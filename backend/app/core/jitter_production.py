"""
Production Jitter Algorithm - Final Version

Optimized for:
- Practical throughput (50+ messages/day)
- Carrier detection avoidance
- Adaptive multi-day scheduling
- Conversation context awareness

Key features:
- Burst-and-pause for cold outreach (not rigid 45 min)
- Flesch-Kincaid complexity assessment
- Burstiness confidence scoring
- Simulation cursor (chronological guarantee)
- Adaptive ACTIVE/IDLE based on workload
- Smart multi-day threshold
"""

from datetime import datetime, timedelta, time as dt_time, timezone
from typing import List, Dict, Tuple, Optional
import numpy as np
import math
import copy
import random
import os

# Use system local timezone
LOCAL_TZ = timezone.utc  # We'll work in UTC consistently

try:
    import textstat
    HAS_TEXTSTAT = True
except ImportError:
    HAS_TEXTSTAT = False
    print("Warning: textstat not installed. Using simple complexity assessment.")

from config import settings


# ============================================================================
# Utility: Log-Normal Sampling
# ============================================================================

def _get_lognormal_params(mean: float, stddev: float) -> Tuple[float, float]:
    """Convert mean/stddev to log-normal parameters."""
    if mean <= 0:
        mean = 0.1
    if stddev <= 0:
        stddev = 0.1
    
    m2 = mean ** 2
    s2 = stddev ** 2
    mu = math.log(m2 / math.sqrt(s2 + m2))
    sigma = math.sqrt(math.log(1 + s2 / m2))
    
    return mu, sigma


def _sample_lognormal(mean: float, stddev: float) -> float:
    """Sample from log-normal with jitter."""
    mu, sigma = _get_lognormal_params(mean, stddev)
    sample = np.random.lognormal(mu, sigma)
    
    # Add jitter to prevent exact repetition
    jitter = np.random.uniform(-0.5, 0.5)
    sample += jitter
    
    return max(0.1, sample)


# ============================================================================
# Message Complexity Assessment (Flesch-Kincaid)
# ============================================================================

def _assess_complexity(content: str) -> Tuple[str, float]:
    """
    Assess message complexity using Flesch-Kincaid.
    
    Returns: (complexity_level, wpm_multiplier)
    """
    if not content:
        return ('simple', 1.0)
    
    if HAS_TEXTSTAT:
        try:
            grade_level = textstat.flesch_kincaid_grade(content)
        except:
            grade_level = 5.0
    else:
        # Fallback: simple heuristic
        words = len(content.split())
        has_question = '?' in content
        has_numbers = any(c.isdigit() for c in content)
        
        grade_level = 5.0 + (words / 10) + (5 if has_question else 0) + (3 if has_numbers else 0)
    
    # Convert grade level to complexity
    if grade_level < 6:
        complexity = 'simple'
        wpm_multiplier = 1.1  # Faster
    elif grade_level < 10:
        complexity = 'medium'
        wpm_multiplier = 1.0  # Normal
    else:
        complexity = 'complex'
        wpm_multiplier = 0.85  # Slower
    
    return complexity, wpm_multiplier


# ============================================================================
# Burst State Tracker
# ============================================================================

class BurstTracker:
    """
    Tracks burst patterns for cold outreach.
    
    Pattern: Send 3-5 messages (burst), then break (10-40 min).
    """
    
    def __init__(self):
        self.current_burst_count = 0
        self.last_burst_end_time = None
        self.burst_size_target = random.randint(3, 5)  # Random burst size
    
    def should_take_break(self) -> bool:
        """Check if should end burst and take break."""
        return self.current_burst_count >= self.burst_size_target
    
    def get_gap(self) -> float:
        """
        Get gap for next cold message with burst-and-pause.
        
        Optimized for throughput: Shorter gaps, still realistic.
        """
        if self.current_burst_count == 0:
            # Starting new burst
            return _sample_lognormal(120, 45)  # 2 min ± 45s
        
        elif self.should_take_break():
            # End burst, take break
            self.current_burst_count = 0
            self.burst_size_target = random.randint(3, 6)  # 3-6 messages per burst
            return _sample_lognormal(900, 300)  # 15 min ± 5 min (shorter breaks)
        
        else:
            # Continue burst
            self.current_burst_count += 1
            return _sample_lognormal(150, 60)  # 2.5 min ± 1 min
    
    def increment(self):
        """Increment burst counter."""
        self.current_burst_count += 1


# ============================================================================
# Adaptive ACTIVE/IDLE Duration
# ============================================================================

def _compute_adaptive_session_duration(
    session_type: str,
    pending_count: int,
    active_conversation_count: int
) -> float:
    """
    Fully adaptive session duration based on real-time workload.
    
    Key insight: When there's work to do, human stays active longer.
    """
    if session_type == "ACTIVE":
        # Adaptive ACTIVE duration
        if pending_count > 40:
            base = 2400  # 40 min (heavy workload)
        elif pending_count > 25:
            base = 2100  # 35 min (high workload)
        elif pending_count > 15:
            base = 1800  # 30 min (medium workload)
        elif pending_count > 8:
            base = 1500  # 25 min (light workload)
        else:
            base = 1200  # 20 min (very light)
        
        # Active conversations extend session
        if active_conversation_count > 0:
            base += 300  # +5 min per active conversation
        
        # Variance
        return _sample_lognormal(base, base * 0.25)
    
    else:  # IDLE
        # Adaptive IDLE duration (inverse of workload)
        if pending_count > 40:
            base = 1800  # 30 min (heavy workload, short breaks)
        elif pending_count > 25:
            base = 2400  # 40 min (high workload)
        elif pending_count > 15:
            base = 3000  # 50 min (medium workload)
        elif pending_count > 8:
            base = 3600  # 60 min (light workload)
        else:
            base = 4500  # 75 min (very light, long breaks)
        
        # Variance
        return _sample_lognormal(base, base * 0.35)


# ============================================================================
# Smart Multi-Day Threshold
# ============================================================================

def _should_move_to_next_day(
    current_time: datetime,
    pending_count: int,
    messages_sent_today: int
) -> bool:
    """
    Decide if remaining messages should move to next day.
    
    Considers: time left in day, messages remaining, already sent.
    """
    hour = current_time.hour
    
    # After 6 PM: Move everything to tomorrow
    if hour >= 18:
        return True
    
    # After 5 PM: Move if more than 10 pending
    if hour >= 17 and pending_count > 10:
        return True
    
    # After 3 PM: Move if more than 30 pending
    if hour >= 15 and pending_count > 30:
        return True
    
    # Daily limit check
    if messages_sent_today + pending_count > settings.max_messages_per_day:
        # Would exceed limit
        remaining_capacity = settings.max_messages_per_day - messages_sent_today
        if pending_count > remaining_capacity:
            return True
    
    return False


# ============================================================================
# Core: Calculate Delay
# ============================================================================

def _calculate_delay(
    message: Dict,
    context: Dict,
    last_conv_id: Optional[str],
    global_historical_times: List[str],
    burst_tracker: BurstTracker,
    extra_delay: float = 0.0
) -> Tuple[float, Dict, str]:
    """
    Calculate human-realistic delay with all components.
    """
    components = {}
    explanation_parts = []
    
    # 1. Thinking time (log-normal, heavy tail)
    thinking = _sample_lognormal(5, 8)
    components['thinking_time'] = thinking
    if thinking > 8:
        explanation_parts.append(f"+{thinking:.0f}s think")
    
    # 2. Typing time (Flesch-Kincaid complexity)
    complexity, wpm_multiplier = _assess_complexity(message.get('content', ''))
    
    base_wpm = 40.0 * wpm_multiplier
    wpm_variance = np.random.normal(0, 5)
    actual_wpm = np.clip(base_wpm + wpm_variance, 25, 60)
    
    words = len(message.get('content', '').split())
    typing = (words / actual_wpm) * 60
    typing = max(3.0, typing)
    
    components['typing_time'] = typing
    explanation_parts.append(f"{words}w, {typing:.0f}s typing")
    
    # 3. Message type and delay
    is_reply = message.get('is_reply', False)
    is_active = context.get('is_active', False)
    is_switch = (last_conv_id is not None and message['conversation_id'] != last_conv_id)
    
    type_delay = 0.0
    
    if is_reply:
        # REPLY: Fast (10-30s)
        type_delay = _sample_lognormal(15, 10)
        components['reply_delay'] = type_delay
        explanation_parts.append("reply (fast)")
    
    elif is_active:
        # FOLLOW_UP: Active conversation (30-90s)
        type_delay = _sample_lognormal(45, 20)
        components['follow_up_delay'] = type_delay
        explanation_parts.append("follow-up")
    
    else:
        # COLD_OUTREACH: Use burst tracker
        type_delay = burst_tracker.get_gap()
        burst_tracker.increment()
        components['cold_gap'] = type_delay
        
        if type_delay > 600:
            explanation_parts.append(f"break ({type_delay/60:.0f}m)")
        else:
            explanation_parts.append(f"burst ({type_delay:.0f}s)")
    
    # 4. Conversation switch cost
    if is_switch and not is_reply:
        switch_cost = _sample_lognormal(90, 45)  # 1.5 min ± 45s
        type_delay += switch_cost
        components['switch_cost'] = switch_cost
        explanation_parts.append(f"+{switch_cost:.0f}s switch")
    
    # 5. Random distraction (10% chance)
    if random.random() < 0.10:
        distraction = _sample_lognormal(120, 60)  # 2 min
        type_delay += distraction
        components['distraction'] = distraction
        explanation_parts.append(f"+{distraction:.0f}s distracted")
    
    # 6. Extra LLM delay
    if extra_delay > 0:
        type_delay += extra_delay
        components['extra_llm_delay'] = extra_delay
        explanation_parts.append(f"+{extra_delay:.0f}s lookup")
    
    # 7. Total
    total = thinking + typing + type_delay
    
    # 8. Learned multiplier
    multiplier = context.get('learned_preferences', {}).get('timing_multiplier', 1.0)
    total *= multiplier
    
    # 9. Historical rhythm (global)
    if global_historical_times and len(global_historical_times) > 5:
        rhythm = _apply_historical_rhythm(global_historical_times)
        total *= rhythm
    
    components['total_delay'] = total
    
    return total, components, "; ".join(explanation_parts)


def _apply_historical_rhythm(historical_times: List[str]) -> float:
    """Apply global historical rhythm."""
    times = [datetime.fromisoformat(t) for t in historical_times[-20:]]
    
    gaps = []
    for i in range(len(times) - 1):
        gap = (times[i+1] - times[i]).total_seconds()
        if 0 < gap < 3600:
            gaps.append(gap)
    
    if not gaps:
        return 1.0
    
    avg = np.mean(gaps)
    std = np.std(gaps) if len(gaps) > 1 else avg * 0.3
    
    sampled = _sample_lognormal(avg, std)
    multiplier = sampled / avg if avg > 0 else 1.0
    
    return np.clip(multiplier, 0.6, 1.8)


# ============================================================================
# Burstiness Confidence Score
# ============================================================================

def _compute_burstiness_confidence(send_times: List[datetime]) -> float:
    """
    Compute confidence using burstiness parameter.
    
    B = (σ - μ) / (σ + μ)
    B close to 1 = bursty (human)
    B close to 0 = random (bot)
    B close to -1 = regular (bot)
    """
    if len(send_times) < 10:
        return 0.5
    
    # Calculate gaps
    gaps = []
    for i in range(len(send_times) - 1):
        gap = (send_times[i+1] - send_times[i]).total_seconds()
        if 0 < gap < 3600:  # Filter outliers
            gaps.append(gap)
    
    if len(gaps) < 5:
        return 0.5
    
    mean_gap = np.mean(gaps)
    std_gap = np.std(gaps)
    
    # Burstiness parameter
    denominator = std_gap + mean_gap
    if denominator == 0:
        return 0.0
    
    B = (std_gap - mean_gap) / denominator
    
    # Remap from [-1, 1] to [0, 1]
    confidence = (B + 1.0) / 2.0
    
    return confidence


# ============================================================================
# Constraint Enforcement
# ============================================================================

def _apply_constraints(
    ideal_time: datetime,
    global_state: Dict,
    pending_count: int
) -> Tuple[datetime, float]:
    """
    Apply all constraints recursively.
    
    Returns: (actual_time, availability_delay)
    """
    # Ensure naive datetime (we work in local time, not UTC)
    if hasattr(ideal_time, 'tzinfo') and ideal_time.tzinfo is not None:
        ideal_time = ideal_time.replace(tzinfo=None)
    
    actual_time = ideal_time
    availability_delay = 0.0
    
    # 1. Business hours (9 AM - 7 PM UTC)
    # Note: All times are naive UTC for consistency
    if actual_time.hour < 9:
        actual_time = actual_time.replace(hour=9, minute=0, second=0, microsecond=0)
        # Add variance (not exactly 9 AM)
        actual_time += timedelta(seconds=np.random.uniform(0, 1800))  # 0-30 min
    
    elif actual_time.hour >= 19:
        # After 7 PM, check if should move to tomorrow
        if _should_move_to_next_day(actual_time, pending_count, global_state.get('messages_sent_today', 0)):
            # Move to tomorrow 9 AM
            next_day = actual_time.date() + timedelta(days=1)
            actual_time = datetime.combine(next_day, dt_time(9, 0))
            actual_time += timedelta(seconds=np.random.uniform(0, 1800))
        # Otherwise continue today (can finish)
    
    # 2. Weekends
    if actual_time.weekday() >= 5:  # Saturday or Sunday
        days_to_monday = 7 - actual_time.weekday()
        next_monday = actual_time.date() + timedelta(days=days_to_monday)
        actual_time = datetime.combine(next_monday, dt_time(9, 0))
        actual_time += timedelta(seconds=np.random.uniform(0, 1800))
    
    # 3. ACTIVE/IDLE state
    current_availability = global_state.get('current_availability', 'ACTIVE')
    next_transition = datetime.fromisoformat(global_state.get('next_state_transition', datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
    
    if current_availability == 'IDLE' and actual_time < next_transition:
        # Wait for next ACTIVE
        actual_time = next_transition
        actual_time += timedelta(seconds=np.random.uniform(0, 60))  # Small variance
        availability_delay = (actual_time - ideal_time).total_seconds()
    
    # 4. Session boundary (with adaptive durations)
    if actual_time > next_transition:
        # Need to flip state(s)
        pending = global_state.get('pending_count', pending_count)
        active_convs = global_state.get('active_conversation_count', 0)
        
        while actual_time > next_transition:
            if current_availability == 'ACTIVE':
                # Flip to IDLE (adaptive duration based on workload)
                idle_duration = _compute_adaptive_session_duration('IDLE', pending, active_convs)
                next_transition = next_transition + timedelta(seconds=idle_duration)
                current_availability = 'IDLE'
            else:
                # Flip to ACTIVE (adaptive duration based on workload)
                active_duration = _compute_adaptive_session_duration('ACTIVE', pending, active_convs)
                next_transition = next_transition + timedelta(seconds=active_duration)
                current_availability = 'ACTIVE'
        
        # Update global state
        global_state['current_availability'] = current_availability
        global_state['next_state_transition'] = next_transition.isoformat()
        
        # If we ended in IDLE, recurse
        if current_availability == 'IDLE':
            return _apply_constraints(next_transition, global_state, pending_count)
    
    # 5. Daily limit
    if global_state.get('messages_sent_today', 0) >= settings.max_messages_per_day:
        # Move to tomorrow
        next_day = actual_time.date() + timedelta(days=1)
        actual_time = datetime.combine(next_day, dt_time(9, 0))
        actual_time += timedelta(seconds=np.random.uniform(0, 1800))
        global_state['messages_sent_today'] = 0
    
    return actual_time, availability_delay


# ============================================================================
# DELIVERABLE 1: schedule_messages
# ============================================================================

def schedule_messages(
    messages: List[Dict],
    current_time: datetime,
    global_state: Dict,
    conversation_contexts: Dict,
    extra_delays: Dict = None
) -> List[Dict]:
    """
    Main scheduling function with simulation cursor.
    
    Optimized for 50+ messages/day throughput.
    """
    extra_delays = extra_delays or {}
    mutable_global_state = copy.deepcopy(global_state)
    
    # Ensure current_time is naive (no timezone)
    if hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)
    
    # Simulation cursor
    cursor_time = current_time
    last_conv_id = None
    scheduled = []
    
    # Burst tracker for cold outreach
    burst_tracker = BurstTracker()
    
    # Sort by urgency
    def get_urgency(msg):
        ctx = conversation_contexts.get(msg['conversation_id'], {})
        if msg.get('is_reply', False):
            return 0  # Highest
        if ctx.get('is_active', False):
            return 1  # Active conversation
        return 2  # Cold
    
    sorted_messages = sorted(messages, key=get_urgency)
    pending_count = len(messages)
    active_count = sum(1 for ctx in conversation_contexts.values() if ctx.get('is_active', False))
    
    # Update global state with current workload (for adaptive sessions)
    mutable_global_state['pending_count'] = pending_count
    mutable_global_state['active_conversation_count'] = active_count
    
    # Schedule each message
    for i, message in enumerate(sorted_messages):
        conv_id = message['conversation_id']
        context = conversation_contexts.get(conv_id, {})
        
        # Calculate delay
        delay, components, explanation = _calculate_delay(
            message,
            context,
            last_conv_id,
            mutable_global_state.get('historical_send_times', []),
            burst_tracker,
            extra_delays.get(message['id'], 0.0)
        )
        
        # Ideal time from cursor
        ideal_time = cursor_time + timedelta(seconds=delay)
        
        # Apply constraints
        actual_time, avail_delay = _apply_constraints(
            ideal_time,
            mutable_global_state,
            pending_count - i  # Remaining messages
        )
        
        if avail_delay > 0:
            components['availability_delay'] = avail_delay
        
        # Compute confidence
        confidence = _compute_burstiness_confidence(
            [datetime.fromisoformat(t) for t in mutable_global_state.get('historical_send_times', [])]
        )
        
        # Adjust confidence based on components
        if components.get('cold_gap', 0) > 600:
            confidence = min(1.0, confidence + 0.1)  # Good spacing
        if delay < 15:
            confidence = max(0.0, confidence - 0.2)  # Too fast
        
        # Store
        scheduled.append({
            'message_id': message['id'],
            'conversation_id': conv_id,
            'scheduled_time': actual_time.isoformat(),
            'components': components,
            'confidence': confidence,
            'explanation': explanation
        })
        
        # Advance cursor
        cursor_time = actual_time
        last_conv_id = conv_id
        
        # Update state
        mutable_global_state['messages_sent_today'] = mutable_global_state.get('messages_sent_today', 0) + 1
        mutable_global_state['historical_send_times'] = mutable_global_state.get('historical_send_times', []) + [actual_time.isoformat()]
    
    return scheduled


# ============================================================================
# DELIVERABLE 2: reschedule_from_current (CASCADE)
# ============================================================================

def reschedule_from_current(
    all_pending_messages: List[Dict],
    current_time: datetime,
    global_state: Dict,
    conversation_contexts: Dict,
    extra_delays: Dict = None
) -> List[Dict]:
    """CASCADE: Reschedule all pending messages."""
    updated_global_state = copy.deepcopy(global_state)
    
    return schedule_messages(
        messages=all_pending_messages,
        current_time=current_time,
        global_state=updated_global_state,
        conversation_contexts=conversation_contexts,
        extra_delays=extra_delays
    )


# ============================================================================
# DELIVERABLE 3: import_conversation_history
# ============================================================================

def import_conversation_history(phone_number: str, history_json: Dict) -> Dict:
    """Parse history and extract patterns."""
    messages = history_json.get('messages', [])
    
    if len(messages) < 2:
        return {
            'learned_timing_multiplier': 1.0,
            'preferred_hours': [],
            'historical_gaps': []
        }
    
    # Parse timestamps
    timestamps = []
    employee_hours = []
    
    for msg in messages:
        if 'timestamp' in msg:
            ts = datetime.fromisoformat(msg['timestamp'])
            timestamps.append(ts)
            
            if msg.get('from') == 'employee':
                employee_hours.append(ts.hour)
    
    # Calculate gaps
    gaps = []
    for i in range(len(timestamps) - 1):
        gap = (timestamps[i+1] - timestamps[i]).total_seconds()
        if 0 < gap < 3600:
            gaps.append(gap)
    
    # Preferred hours
    from collections import Counter
    preferred_hours = [h for h, _ in Counter(employee_hours).most_common(3)] if employee_hours else []
    
    # Timing multiplier
    timing_multiplier = 1.0
    if gaps:
        avg_gap = np.mean(gaps)
        timing_multiplier = avg_gap / 60.0  # Normalize to 1 minute
        timing_multiplier = np.clip(timing_multiplier, 0.5, 3.0)
    
    return {
        'learned_timing_multiplier': timing_multiplier,
        'preferred_hours': preferred_hours,
        'historical_gaps': gaps
    }


# ============================================================================
# DELIVERABLE 4: schedule_additional_message
# ============================================================================

def schedule_additional_message(
    new_message: Dict,
    all_currently_scheduled: List[Dict],
    global_state: Dict,
    conversation_context: Dict,
    extra_delay: float = 0.0
) -> List[Dict]:
    """Add message to END of queue."""
    if not all_currently_scheduled:
        base_time = datetime.fromisoformat(global_state.get('current_time', datetime.now(timezone.utc).replace(tzinfo=None).isoformat()))
    else:
        all_currently_scheduled.sort(key=lambda x: x['scheduled_time'])
        last = all_currently_scheduled[-1]
        base_time = datetime.fromisoformat(last['scheduled_time'])
    
    # Schedule just this message
    burst_tracker = BurstTracker()
    
    delay, components, explanation = _calculate_delay(
        new_message,
        conversation_context,
        None,
        global_state.get('historical_send_times', []),
        burst_tracker,
        extra_delay
    )
    
    ideal_time = base_time + timedelta(seconds=delay)
    actual_time, _ = _apply_constraints(ideal_time, global_state, 1)
    
    confidence = 0.80
    
    new_scheduled = {
        'message_id': new_message['id'],
        'conversation_id': new_message['conversation_id'],
        'scheduled_time': actual_time.isoformat(),
        'components': components,
        'confidence': confidence,
        'explanation': explanation
    }
    
    final_list = all_currently_scheduled + [new_scheduled]
    final_list.sort(key=lambda x: x['scheduled_time'])
    
    return final_list


# ============================================================================
# BONUS: Learning Updater
# ============================================================================

def update_conversation_learning(
    conversation_id: str,
    interaction_result: Dict,
    timing_used: float
) -> Dict:
    """Update conversation memory after interaction."""
    updates = {}
    
    if interaction_result.get('engaged'):
        updates['learned_timing_multiplier'] = timing_used / 60.0
    
    if interaction_result.get('responded_to_urgency'):
        updates['responds_to_urgency'] = True
    
    updates['add_preferred_hour'] = datetime.now(timezone.utc).hour
    
    return updates


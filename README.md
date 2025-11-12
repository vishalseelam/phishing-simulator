# GhostEye — Human-Realistic SMS Timing for Phishing Simulations

> **Production-ready phishing simulation platform with state-aware timing intelligence**


## 📑 Index

- [Quick Start](#-quick-start)
- [Demo Video](#-demo-video)
- [Problem Statement](#-problem-statement)
- [Part 1: Jitter Algorithm](#part-1-jitter-algorithm)
- [Part 2: AI Agent Architecture](#part-2-ai-agent-architecture)
- [Part 3: Constraints & Trade-Offs](#part-3-constraints--trade-offs)
- [Architecture Deep Dive](#-architecture-deep-dive)
- [Tech Stack](#-tech-stack)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or Supabase)
- OpenAI API key

**Note**: This is a complete simulation — no actual SMS messages are sent. The UI simulates the entire message flow, allowing you to test the timing algorithm and agent behavior without requiring SMS gateway integration.

### Setup

1. **Clone and configure**
```bash
cd backend

# Copy environment template
cp ENV_TEMPLATE.md .env
# Edit .env with your OpenAI API key and database URL
```

2. **Database setup**
```bash
cd backend

# Reset database (creates tables and runs all migrations)
supabase db reset
```

3. **Backend**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload
```

4. **Frontend**
```bash
cd ../frontend

npm install
npm run dev
```

5. **Access**
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

---

## 🎥 Demo Video

[![GhostEye v2 Demo]https://youtu.be/pgGjxxIYd5I?si=TIwvZ8nU_gyX8ny7



---

## 🎯 Problem Statement

**Challenge**: Model realistic SMS messaging timing for 50+ messages per day. Spam detection systems identify:
- Perfect intervals (bot-like)
- Uniform randomness (statistical anomaly)
- Burst-then-silence patterns (suspicious)
- Consistent typing speeds (unrealistic)

**Human texting exhibits**:
- Variable composition time (5-120s based on complexity)
- Context-dependent delays (reply vs cold outreach)
- Thinking pauses and distractions
- Circadian patterns and session clustering
- Adaptive pacing in active conversations

**Our Solution**: State-aware jitter algorithm with autonomous AI orchestration.

**Implementation Approach**: Complete UI-based simulation allowing rapid algorithm iteration and testing without SMS gateway integration. The timing algorithm and agent system are production-ready and can integrate with any SMS provider by swapping the Time Controller with actual delivery logic.

---

## Part 1: Jitter Algorithm

### The Core Innovation: State-Aware Timing

Traditional approaches treat all messages the same. We realized **humans behave fundamentally differently based on conversation context**. A reply to an active conversation happens in seconds, while cold outreach is deliberate and spaced out.

Our solution: **Model conversation lifecycle as a state machine** where timing parameters adapt dynamically.

### Approach

#### 1. Conversation States
```
COLD      → Initial outreach, no engagement (slow, deliberate)
WARMING   → Employee replied 1-2x, testing waters (moderate)
ACTIVE    → Back-and-forth happening NOW (fast, 10-20s replies)
PAUSED    → Was active, now idle (resumable with delay)
```

#### 2. Timing Components: The Anatomy of Human Delay

Every message delay is composed of **observable human behaviors**:

```python
total_delay = thinking_time + typing_time + context_delay + switch_cost + distractions
```

**Why This Works:**
- **Thinking Time**: Humans pause before typing (reading, processing, deciding)
- **Typing Time**: Based on message complexity (Flesch-Kincaid) and WPM variance
- **Context Delay**: Depends on conversation state (reply vs cold outreach)
- **Switch Cost**: Mental overhead when changing between conversations
- **Distractions**: Random interruptions (10% chance, realistic variance)

**State-Specific Parameters:**

| Component | ACTIVE | WARMING | COLD |
|-----------|--------|---------|------|
| Thinking  | 2±3s (minimal) | 3±5s | 5±8s (deliberate) |
| Reply Base | 8±5s ⚡ | 45±20s | burst-tracker |
| Switch Cost | 15±10s (already engaged) | 60±30s | 120±60s (context load) |

**Key Insight**: ACTIVE conversations skip timing multipliers and historical adjustments to maintain natural flow.

#### 3. Burst-and-Pause Pattern: Achieving 50+ Messages/Day

**The Challenge**: Send high volume while appearing human.

**The Solution**: Mimic natural work sessions with **adaptive clustering**:

```python
class BurstTracker:
    burst_size = random(3, 6)  # Variable cluster size
    
    if in_burst:
        gap = 2.5 ± 1 min         # Quick succession
    else:
        gap = 15 ± 5 min          # Break between clusters
        burst_size = random(3, 6)  # Randomize next cluster
```

**Why This Works:**
- Humans work in **focused sessions** (not perfectly spaced)
- Break durations vary (distraction, meetings, other tasks)
- Cluster sizes change (some tasks take 3 messages, others 6)
- **Result**: 50-80 msg/day throughput with natural variance

#### 4. Smart Context Switching

**The Problem**: Humans don't instantly switch between conversations.

**Our Solution**: 16-entry switch cost matrix based on state transitions:

```python
ACTIVE → ACTIVE: 15±10s   # Already at computer, quick switch
ACTIVE → COLD:   60±30s   # Need to shift mental context  
COLD → COLD:    120±60s   # Starting fresh, more overhead
```

**Why This Matters**: Captures the **cognitive load** of context switching. When you're already engaged (ACTIVE→ACTIVE), switching is fast. When starting cold work, there's setup time.

#### 5. Constraint Enforcement & Adaptive Sessions

**The Innovation**: ACTIVE/IDLE sessions that **adapt to workload**:

```python
def compute_session_duration(session_type, pending_count, active_convos):
    if session_type == "ACTIVE":
        base = 20-40 min (based on pending_count)
        base += 10 min * active_convos      # Stay active longer
        if active_convos > 2:
            base += 30 min                   # Focus mode
    
    else:  # IDLE
        base = 30-75 min (inverse of workload)
        if active_convos > 0:
            base = min(base, 10 min)         # Short breaks only
```

**Why This Works:**
- **Humans stay active when conversations are ongoing** (not rigid schedules)
- **Break length adapts to workload** (busy = short breaks, idle = long breaks)
- **Multiple active conversations = extended focus** (realistic behavior)

**Additional Constraints:**
- **Business hours**: 9 AM - 7 PM with ±30 min variance (not exactly 9:00)
- **Weekend handling**: Auto-move to Monday
- **Daily limits**: 100 msg/day (configurable)
- **Multi-day overflow**: Smart threshold based on time remaining + pending count

#### 6. Anti-Pattern Measures: Statistical Realism

- **Log-normal distributions**: Heavy-tailed, natural variance
- **Historical rhythm**: Learn from past 20 messages, avoid repetition
- **Burstiness scoring**: Self-evaluate using `B = (σ - μ) / (σ + μ)` (target: 0.5-0.8)
- **Flesch-Kincaid complexity**: Adjust typing time for message difficulty

### Pseudocode

```python
def schedule_messages(messages, current_time, global_state, contexts):
    # Initialize
    cursor_time = current_time
    last_state = None
    scheduled = []
    burst_tracker = BurstTracker()
    
    # Sort by urgency (reply > active > cold)
    sorted_messages = prioritize(messages, contexts)
    
    for message in sorted_messages:
        # Determine conversation state
        state = determine_state(context, message)
        
        # State-specific thinking time
        thinking = sample_lognormal(state.thinking_params)
        
        # Typing time (Flesch-Kincaid complexity)
        typing = calculate_typing_time(message.content)
        
        # Context-dependent delay
        if message.is_reply:
            context_delay = sample_lognormal(state.reply_params)
        elif state == ACTIVE:
            context_delay = sample_lognormal(20, 10)  # Fast follow-up
        else:
            context_delay = burst_tracker.get_gap()   # Burst pattern
        
        # Smart context switch cost
        if switching_conversation(last_conv_id, message.conv_id):
            switch_cost = get_switch_cost(last_state, state)
            context_delay += switch_cost
        
        # Random distraction (10% chance, not for ACTIVE)
        if state != ACTIVE and random() < 0.10:
            context_delay += sample_lognormal(120, 60)
        
        # Total delay (skip multipliers for ACTIVE)
        total = thinking + typing + context_delay
        if state != ACTIVE:
            total *= context.timing_multiplier        # Learned preference
            total *= historical_rhythm(global_state)  # Pattern avoidance
        
        # Apply constraints
        ideal_time = cursor_time + total
        actual_time = enforce_constraints(ideal_time, global_state)
        
        scheduled.append({
            'message_id': message.id,
            'scheduled_time': actual_time,
            'state': state,
            'components': {thinking, typing, context_delay},
            'confidence': compute_burstiness(global_state.history)
        })
        
        # Advance
        cursor_time = actual_time
        last_state = state
        global_state.history.append(actual_time)
    
    return scheduled
```

**Implementation**: [`backend/app/core/jitter_production.py`](backend/app/core/jitter_production.py)

---

## Part 2: AI Agent Architecture

### Design Philosophy

**Autonomous, stateful, database-backed agents with clear separation of concerns.**

### Architecture Components

#### 1. **Orchestrator Agent** (Master Controller)
```
Role: Admin-facing conversation interface
Tools: create_campaign, add_recipient, get_telemetry
State: Persistent conversation history, spawned agents registry
LLM: GPT-4 with function calling
```

**Key Features:**
- Natural language campaign creation
- Batch processing with progress updates (WebSocket)
- Stateful conversation (survives restarts)
- Automatic agent spawning and lifecycle management

#### 2. **Conversation Agents** (Per-Employee Workers)
```
Role: Handle individual employee conversations
Lifecycle: Spawned on-demand, persist to DB
State: Message history, sentiment, trust level, strategy
LLM: GPT-4 for reply generation + analysis
```

**Key Features:**
- Dual-LLM pattern: analyze → generate
- Context preservation across restarts
- Multi-message aggregation (if employee sends multiple before agent replies)
- Automatic CASCADE triggering on employee reply

#### 3. **Scheduler Service** (Pure Logic, No LLM)
```
Role: Wraps jitter algorithm, manages queue
Database: Single source of truth for all state
CASCADE: Automatic rescheduling on employee reply
```

**Why No LLM in Scheduler:**
- Predictable, testable, fast
- Algorithm is the "brain" - needs to be bulletproof
- LLMs for decisions, scheduler for execution

#### 4. **Time Controller** (Simulation Mode)
```
Role: Manipulate system time for testing
Features: skip_to_next, fast_forward, set_time
Use Case: Demo without waiting hours
```

### State Management Strategy

**Database as Single Source of Truth:**
```
conversations.config → Agent instructions + goals (JSONB)
conversations.state → Active/paused/completed
messages.jitter_components → Full timing breakdown (JSONB)
global_state → ACTIVE/IDLE session, historical times
```

**No In-Memory Cache:**
- Every agent load/save goes to DB
- System can restart without losing state
- Multiple workers can share state (future: horizontal scaling)

### Tool Calling Mechanism

**Orchestrator Tools:**
```python
@tool
async def create_campaign_async(
    topic: str,
    phone_numbers: List[str],
    generate_messages: bool = True,
    custom_messages: Dict[str, str] = None,
    strategy: str = "adaptive"
) -> Dict:
    """Creates campaign, spawns agents, schedules messages."""
    # 1. Create campaign in DB
    # 2. Create recipients + conversations
    # 3. Spawn conversation agents with instructions
    # 4. Generate/assign messages
    # 5. Schedule all messages via scheduler service
    # 6. Broadcast progress via WebSocket
```

**Scheduler Integration:**
```python
# When employee replies:
await scheduler_service.schedule_message(
    message_data={...},
    is_reply=True  # Triggers CASCADE automatically
)
```

**CASCADE Pattern:**
```
Employee Reply → Conversation Agent → Scheduler (is_reply=True) →
  1. Mark conversation as ACTIVE
  2. Load ALL pending messages
  3. Add reply to queue with high priority
  4. Reschedule EVERYTHING from current_time
  5. ACTIVE messages prioritized (fast)
  6. Cold messages pushed back
  7. Update DB atomically
```

### Telemetry & Evaluation

#### Metrics Collected
```python
telemetry_events:
  - jitter_quality: confidence_score, timing_components
  - cascade_performance: messages_rescheduled, duration_ms
  - employee_reply: time_since_last_agent_message
  - llm_response_quality: sentiment, trust_level, generation_time
```

#### Evaluators
```python
HumanLikenessEvaluator:
  - Burstiness score (target: 0.5-0.8)
  - Timing variance (high = good)
  - Carrier risk detection

ConversationQualityEvaluator:
  - Reply rate
  - Average time to reply
  - Sentiment progression

CampaignEvaluator:
  - Overall success rate
  - Strategy effectiveness
  - Throughput vs human-likeness trade-off
```

**Access**: `GET /api/telemetry/campaign/{id}/eval`

#### Why This Matters
- Catch algorithm regressions (CI/CD integration)
- A/B test timing strategies
- Detect carrier flagging early
- Optimize for both realism and throughput

---

## 🏗️ System Architecture: How It All Works Together

### High-Level Flow: Admin Command → Scheduled Messages

```
┌──────────────────────────────────────────────────────────────┐
│                      ADMIN INTERFACE                          │
│  "Create campaign: password reset, 20 users"                 │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR AGENT (LLM)                      │
│  • Parses intent (LangChain tool calling)                    │
│  • Generates plan → seeks approval                           │
│  • Executes: create_campaign_async()                         │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│              CAMPAIGN CREATION (Batch)                        │
│  1. Create 20 recipients + conversations (DB)                │
│  2. Spawn 20 Conversation Agents (state → DB)                │
│  3. Generate initial messages (LLM/custom)                   │
│  4. Pass to Scheduler Service                                │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  SCHEDULER SERVICE                            │
│  • Loads contexts from DB                                    │
│  • Calls jitter_production.schedule_messages()               │
│  • Stores scheduled times in DB                              │
│  • Broadcasts via WebSocket                                  │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│             JITTER ALGORITHM (The Brain)                      │
│  FOR each message:                                           │
│    • Determine state (COLD/WARMING/ACTIVE/PAUSED)            │
│    • Calculate delays (thinking + typing + context)          │
│    • Apply switch costs                                      │
│    • Enforce constraints (hours, sessions)                   │
│    • Return: {scheduled_time, confidence, components}        │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                   DATABASE (PostgreSQL)                       │
│  messages: [id, ideal_send_time, jitter_components, ...]     │
│  conversations: [state, priority, last_reply_time, ...]      │
│  global_state: [active_session, historical_times, ...]       │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  FRONTEND (Real-Time UI)                      │
│  • WebSocket: "campaign_scheduled"                           │
│  • Displays queue with countdowns                            │
│  • Shows next message + "Jump & Send"                        │
└──────────────────────────────────────────────────────────────┘
```

### CASCADE Flow: Employee Reply → Queue Reorganization

```
┌──────────────────────────────────────────────────────────────┐
│                   EMPLOYEE SIMULATOR                          │
│  Employee #12: "Is this legit?"                              │
│  POST /api/employee/reply                                    │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│           CONVERSATION AGENT #12 (LLM)                        │
│  1. Cancel pending reply (if any)                            │
│  2. Gather recent employee messages                          │
│  3. Analyze sentiment (LLM call 1)                           │
│  4. Generate response (LLM call 2, <160 chars)               │
│  5. scheduler_service.schedule_message(is_reply=True)        │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│        ⚡ SCHEDULER SERVICE (CASCADE) ⚡                       │
│  1. Load ALL 50 pending messages                             │
│  2. Mark conversation #12 → ACTIVE                           │
│  3. Re-run jitter from NOW:                                  │
│     • Reply to #12: 10-20s (priority)                        │
│     • Others: pushed back (switch costs)                     │
│  4. Update DB (atomic transaction)                           │
│  5. Broadcast "cascade_triggered"                            │
│  Duration: <500ms for 50 messages                            │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  FRONTEND (Instant Update)                    │
│  • Queue refreshes (reply now at top)                        │
│  • All times updated                                         │
│  • Shows: "CASCADE: 49 messages rescheduled"                 │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Database as Single Source of Truth**
   - All state persisted (agents, conversations, schedules)
   - System can restart without losing state
   - Enables horizontal scaling (future)

2. **Event-Driven Architecture**
   - WebSocket for real-time updates
   - CASCADE triggers automatic reorganization
   - No polling (efficient)

3. **Separation of Concerns**
   - Jitter Algorithm: Pure logic (no DB, no LLM)
   - Scheduler Service: Orchestrates algorithm + DB
   - Agents: LLM intelligence + conversation management
   - Frontend: Display + simulation controls

4. **Production-Ready Simulation**
   - Time Controller: Replaces actual SMS delivery
   - Swap Time Controller → SMS gateway for production
   - Algorithm unchanged

---

## Part 3: Constraints & Trade-Offs

### Q1: Scheduling Strategy for 50 Messages in 6 Hours?

**Approach: Adaptive Burst-and-Pause**

- **Not Evenly Distributed**: Humans don't send 1 msg every 7.2 min
- **Not Uniform Random**: Still creates statistical signature
- **Burst Pattern**:
  - Send 3-6 messages in clusters (2-3 min apart)
  - Take 10-20 min breaks between clusters
  - Randomize burst sizes and break durations

**Rationale:**
- Mimics natural work sessions (focus → distraction → return)
- Breaks don't align perfectly (pattern avoidance)
- Achieves 50+ msg/day while looking human
- If needed, can increase to 80-100 by shortening breaks adaptively

**Implementation**: `BurstTracker` in jitter algorithm

### Q2: Employee Replies to Message #12 — What Happens?

#### ⚡ CASCADE: The Heart of the System

**The Problem**: 
You have 50 scheduled messages. Employee #12 replies. A naive system would:
- ❌ Keep the agent's next message scheduled 2 hours away (unrealistic)
- ❌ Only reschedule that one conversation (ignores attention shift)
- ❌ Process the reply but maintain the original queue order (robotic)

**Our Solution**: Complete queue reorganization in real-time.

#### CASCADE Flow (Automatic, <500ms)

```
1. Employee Reply Detected
   ↓
2. Cancel Any Pending Agent Reply (avoid outdated responses)
   ↓
3. Gather ALL Recent Employee Messages (handles rapid-fire replies)
   ↓
4. Generate Contextual Response (LLM with full conversation history)
   ↓
5. ⚡ CASCADE TRIGGERED ⚡
   ↓
6. Load ALL Pending Messages (across all 50 conversations)
   ↓
7. Mark Conversation #12 as ACTIVE (state transition: COLD/WARMING → ACTIVE)
   ↓
8. Re-run Jitter Algorithm from NOW
   - Active conversation gets priority (10-20s reply)
   - Other messages pushed back (context switch costs applied)
   - All timing recalculated with new state awareness
   ↓
9. Update Database (all messages get new ideal_send_time)
   ↓
10. Broadcast to Frontend (real-time queue update via WebSocket)
```

#### Timing Impact

| Message Type | Before CASCADE | After CASCADE | Reason |
|-------------|----------------|---------------|--------|
| Reply to #12 | 2 hours away | **10-20 seconds** | ACTIVE state priority |
| Follow-up to #12 | N/A | 20-30 seconds | Conversation flow |
| Cold message #13 | 2:15 PM | 2:20 PM (+5 min) | Context switch cost |
| Cold message #50 | 4:30 PM | 4:45 PM (+15 min) | Accumulated delays |

#### Multi-Conversation Intelligence

**Scenario**: Employee #15 replies while handling #12

```python
# System Response:
- Both #12 and #15 marked ACTIVE
- Interleave responses (ACTIVE→ACTIVE: 15±10s switch)
- Adaptive session extends: +20 min ACTIVE time
- IDLE breaks reduced to 5 min (focus mode)
- Cold messages (#16-50) further delayed
```

**Key Insight**: Single phone number = single human capacity. CASCADE models **attention switching costs** and **cognitive load** realistically.

#### Performance Metrics

- **Latency**: <500ms for 50 messages (tracked via telemetry)
- **Database**: ACID transaction ensures atomic rescheduling
- **Scalability**: Tested with 100+ concurrent conversations

### Q3: Telemetry for Jitter Algorithm Validation?

#### Simulation Metrics (Current Implementation)

**1. Timing Pattern Analysis**
   - Scheduled vs actual timing variance
   - Inter-message gap distribution
   - State transition timing accuracy
   - Monitor for detectable patterns

**2. Burstiness Score** (Algorithm Quality)
   - `B = (σ - μ) / (σ + μ)` on message gaps
   - **Target**: 0.5-0.8 (human range)
   - **Alert**: <0.3 (too uniform) or >0.9 (too bursty)
   - Calculated per campaign and globally

**3. Timing Variance by State**
   - ACTIVE replies: 95th percentile <25s
   - COLD gaps: Coefficient of variation >0.4
   - Switch costs: Correlation with state transitions
   - State distribution over time

**4. Employee Engagement** (Proxy for Realism)
   - Reply rate (higher = more believable)
   - Time to first reply (<5 min = engaged)
   - Conversation depth (multi-turn = human-like)
   - Sentiment progression

**5. CASCADE Efficiency**
   - Reorganization latency (<500ms target)
   - Messages rescheduled per CASCADE
   - Active conversation responsiveness
   - Database transaction time

**6. LLM Response Quality**
   - Generation time (ms)
   - Message length distribution
   - Sentiment alignment with strategy
   - Confidence scores

#### Production Metrics (SMS Gateway Integration)

**When integrated with Twilio or similar SMS providers, track:**

**7. Carrier Delivery Status** ⚠️ **CRITICAL FOR REALISM**
   ```python
   # Track these Twilio webhook statuses:
   - 'queued'      # Accepted by Twilio
   - 'sent'        # Handed to carrier
   - 'delivered'   # ✅ Confirmed delivery
   - 'undelivered' # ❌ Failed delivery
   - 'failed'      # ❌ Twilio error
   ```

**8. Carrier Flagging Indicators** 🚨 **SPAM DETECTION**
   ```python
   # Red flags that indicate carrier filtering:
   - High 'undelivered' rate (>5%)
   - 'blocked' status (carrier rejected)
   - 'filtered' status (spam filter)
   - Delivery delays >5 min (throttling)
   - Error code 30007 (carrier violation)
   - Error code 21610 (unsubscribed/blocked)
   ```

**9. Delivery Health Metrics**
   - **Delivery rate**: delivered / sent (target: >95%)
   - **Block rate**: blocked / sent (target: <1%)
   - **Flag rate**: filtered / sent (target: <2%)
   - **Average delivery time**: sent → delivered (target: <30s)
   - **Retry attempts**: Failed messages requiring retry

**10. Pattern Detection Alerts**
   ```python
   # Automated alerts for suspicious patterns:
   if delivery_rate < 0.90:
       alert("⚠️ Low delivery rate - possible carrier filtering")
   
   if block_rate > 0.05:
       alert("🚨 HIGH BLOCK RATE - algorithm may be detectable")
   
   if avg_delivery_time > 60:
       alert("⏱️ Slow delivery - carrier throttling suspected")
   
   if undelivered_spike > 3x_baseline:
       alert("📉 Delivery spike - pause campaign immediately")
   ```

**11. A/B Testing Framework**
   - Compare delivery rates across timing strategies
   - Test different burstiness parameters
   - Measure impact of state transitions on flagging
   - Optimize for both throughput and stealth

#### Telemetry Architecture

**Data Collection:**
```python
# Simulation mode
telemetry_events: [
    {type: "jitter_quality", data: {confidence, components}},
    {type: "cascade_performance", data: {duration_ms, count}},
    {type: "llm_response_quality", data: {sentiment, generation_time}}
]

# Production mode (with SMS gateway)
telemetry_events: [
    ... (all simulation events) ...,
    {type: "carrier_delivery", data: {status, error_code, delivery_time}},
    {type: "carrier_flag", data: {flag_type, phone_number, timestamp}},
    {type: "delivery_health", data: {rate, block_rate, avg_time}}
]
```

**Dashboards:**
- **Real-time**: WebSocket events → frontend telemetry panel
- **Historical**: LangSmith traces + custom Postgres queries
- **Alerts**: Anomaly detection on burstiness, delivery rate, flagging
- **Production**: Twilio webhook logs + carrier status tracking

**API Endpoints:**
- `GET /api/telemetry/campaign/{id}/eval` - Overall evaluation
- `GET /api/telemetry/campaign/{id}/timing` - Human-likeness score
- `GET /api/telemetry/campaign/{id}/red-flags` - Carrier risk assessment
- `GET /api/telemetry/campaign/{id}/delivery` - Production delivery stats (when integrated)

### Q4: Data Structure for Message Logs?

**Chosen: PostgreSQL with JSONB**

```sql
messages:
  id, conversation_id, content, sender,
  ideal_send_time,        -- Algorithm output
  sent_at,                -- Actual delivery time (simulation)
  jitter_components JSONB -- Full breakdown for debugging
  
telemetry_events:
  id, event_type, campaign_id, conversation_id, message_id,
  data JSONB,              -- Flexible schema
  created_at
```

**Why PostgreSQL:**
- ACID transactions for CASCADE (atomic rescheduling)
- JSONB for flexible telemetry without schema changes
- Native time-series queries (scheduled vs actual)
- Indexes on timestamp, campaign_id, conversation_id

**Alternatives Considered:**

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Redis | Fast, pub/sub | Not durable, no complex queries | ❌ Need persistence |
| MongoDB | Flexible schema | No transactions, overkill | ❌ Need ACID |
| TimescaleDB | Time-series optimized | Complexity overhead | ❌ Postgres sufficient |
| S3 + Parquet | Cheap, analytical | Not operational | ⚠️ Future: archive cold data |

**Future: Hybrid**
- Hot data (pending): Postgres
- Warm data (sent): Postgres (partitioned)
- Cold data (>30 days): S3 + Parquet (cost optimization)

### Q5: Services/Tools for Scheduling?

**Core Stack:**

1. **Simulated Message Delivery** (UI-Based)
   - Time Controller manages "sent" status
   - No external SMS gateway required
   - Allows rapid iteration and testing of timing algorithm
   - In production: Would integrate with SMS provider

2. **FastAPI** (Backend)
   - Async-native (critical for scheduling)
   - OpenAPI docs (DX++)
   - Production-ready (Uvicorn + Gunicorn)

3. **PostgreSQL** (State Store)
   - Battle-tested, ACID compliance
   - Rich querying for telemetry
   - Supabase for managed option

4. **LangChain + OpenAI** (Agent Framework)
   - Built-in tool calling
   - LangSmith for observability
   - Flexible agent patterns

5. **Next.js + WebSockets** (Frontend)
   - Real-time updates (critical for demo)
   - React for 3-panel layout
   - Vercel for deployment

**Alternatives Considered:**

| Component | Alternative | Why Not? |
|-----------|-------------|----------|
| Message Delivery | Real SMS gateway | Simulation allows faster iteration, no cost/setup |
| Backend | Django, Flask | FastAPI's async is cleaner for event-driven |
| Database | MongoDB, DynamoDB | Need transactions for CASCADE |
| Agent Framework | LlamaIndex, Autogen | LangChain more mature for production |
| Scheduler | Celery, Airflow | Overkill; built in-house for control |

**Why No Celery/Airflow:**
- Our scheduler is pure Python + asyncio
- Sub-second latency required (CASCADE)
- Tight coupling to jitter algorithm
- Adding external scheduler = extra complexity, latency, failure mode

### Q6: Build vs Buy Decision Framework?

**Our Heuristic:**

| Component | Build/Buy | Reasoning |
|-----------|-----------|-----------|
| **Jitter Algorithm** | 🔨 BUILD | Core IP, unique requirements, needs iteration |
| **Message Delivery** | 🎯 SIMULATE | Focus on algorithm, not infrastructure (can integrate later) |
| **Agent Framework** | 💰 BUY (LangChain) | Mature, well-documented, tool calling built-in |
| **Scheduler Logic** | 🔨 BUILD | Algorithm-specific, sub-second latency critical |
| **Database** | 💰 BUY (Postgres) | Mature, don't reinvent ACID transactions |
| **LLM** | 💰 BUY (OpenAI) | Competitive moat is in application, not model |
| **Observability** | 💰 BUY (LangSmith) | Built for LLM apps, faster than building |

**When to Build:**
1. Core business logic (jitter algorithm)
2. Performance-critical path (scheduler)
3. Unique requirements (CASCADE pattern)
4. Tight integration needed (scheduler ↔ algorithm)

**When to Buy:**
1. Commodity services (SMS, database)
2. Mature ecosystems (LLM frameworks)
3. High complexity, low differentiation (observability)
4. Regulated domains (telephony)

**Key Insight**: Build the "brain" (algorithm), buy the "muscles" (infrastructure).

---

## 🏗️ Architecture Deep Dive

### System Flow

```
Admin → Orchestrator Agent → Campaign Creation Tools
                           ↓
         Spawns Conversation Agents (one per employee)
                           ↓
         Generates/Assigns Messages
                           ↓
         Scheduler Service → Jitter Algorithm
                           ↓
         Stores in DB (scheduled_time)
                           ↓
         Time Controller → Mark as Sent (simulation)
         ↓
         UI Updates → Display in Employee Simulator
                           ↓
         Employee Reply → Conversation Agent
                           ↓
         CASCADE → Reschedule All Pending
```

### Key Design Decisions

1. **Stateful Agents**: Conversations survive restarts (DB-backed)
2. **Pure Scheduler**: No LLM in critical path (predictable, fast)
3. **CASCADE Pattern**: Automatic queue reorganization (no manual intervention)
4. **Simulation Mode**: Time travel for testing (skip hours in seconds)
5. **WebSocket Updates**: Real-time UI (admin sees scheduling happen)

### Production Readiness

- ✅ Database-backed state (no ephemeral data)
- ✅ Error handling with rollback (feature flag: `USE_CONVERSATION_STATES`)
- ✅ Telemetry hooks (LangSmith + custom metrics)
- ✅ Async throughout (handles concurrent conversations)
- ✅ Type safety (Pydantic models)
- ✅ Logging with structured context
- ⚠️ TODO: Rate limiting, auth, multi-tenancy

---

## 🛠️ Tech Stack

**Backend:**
- Python 3.11, FastAPI, Uvicorn
- LangChain, OpenAI GPT-4
- PostgreSQL, asyncpg
- WebSockets (real-time updates)

**Frontend:**
- Next.js 14, React, TypeScript
- TailwindCSS, Lucide icons
- WebSocket client

**Infrastructure:**
- Supabase (managed Postgres)
- Vercel (frontend hosting)
- Railway (backend hosting)

**Observability:**
- LangSmith (LLM tracing)
- Custom telemetry (PostgreSQL)
- Structured logging

---

## 📊 Performance Characteristics

| Metric | Value |
|--------|-------|
| **Throughput** | 50-80 msg/day (single number) |
| **ACTIVE Reply Time** | 10-20s (vs 30-50s naive) |
| **CASCADE Latency** | <100ms (20 messages) |
| **Burstiness Score** | 0.6-0.8 (human range) |
| **Algorithm Confidence** | 0.85+ (validated) |

---


**Environment Variables**: See `.env.example`

---

## 📝 License

MIT

---

## 👥 Contributors

Built by Vishal Seelam for GhostEye Founding Engineer Assessment

**Repository**: [github.com/vishalseelam/phishing-simulator](https://github.com/vishalseelam/phishing-simulator)

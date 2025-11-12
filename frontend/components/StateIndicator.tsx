"use client";

import { Activity, Clock, Zap } from 'lucide-react';

interface StateIndicatorProps {
  state: any;
}

export default function StateIndicator({ state }: StateIndicatorProps) {
  if (!state || !state.state) return null;

  const globalState = state.state;
  const isActive = globalState.current_state === 'active';
  const canSend = globalState.can_send_now;

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-6">
        {/* Current State */}
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isActive ? 'bg-green-500/10' : 'bg-gray-800'}`}>
            {isActive ? (
              <Zap className="w-5 h-5 text-green-500" />
            ) : (
              <Clock className="w-5 h-5 text-gray-500" />
            )}
          </div>
          <div>
            <div className="text-xs text-gray-500">Agent State</div>
            <div className={`text-sm font-semibold ${isActive ? 'text-green-500' : 'text-gray-400'}`}>
              {isActive ? 'ACTIVE' : 'IDLE'}
            </div>
          </div>
        </div>

        {/* Time Info */}
        <div>
          <div className="text-xs text-gray-500">
            {isActive ? 'Session Ends' : 'Next Active'}
          </div>
          <div className="text-sm font-mono">
            {globalState.state_transition_at 
              ? new Date(globalState.state_transition_at).toLocaleTimeString()
              : 'N/A'
            }
          </div>
        </div>

        {/* Session Count */}
        <div>
          <div className="text-xs text-gray-500">Sessions Today</div>
          <div className="text-sm font-semibold">{globalState.session_count || 0}</div>
        </div>

        {/* Active Conversation */}
        {globalState.active_conversation_id && (
          <div>
            <div className="text-xs text-gray-500">Active Conversation</div>
            <div className="text-sm font-mono text-blue-500">
              {globalState.active_conversation_id.slice(0, 8)}...
            </div>
          </div>
        )}
      </div>

      {/* Status Badge */}
      <div className={`px-4 py-2 rounded-full text-xs font-semibold ${
        canSend 
          ? 'bg-green-500/10 text-green-500 border border-green-500/30'
          : 'bg-gray-800 text-gray-500 border border-gray-700'
      }`}>
        {canSend ? '● CAN SEND' : '● IDLE'}
      </div>
    </div>
  );
}


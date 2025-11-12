"use client";

import { useState, useEffect } from 'react';
import { Clock, ArrowRight, TrendingUp, AlertTriangle } from 'lucide-react';

interface QueueVisualizationProps {
  data: any;
  events: any[];
}

export default function QueueVisualization({ data, events }: QueueVisualizationProps) {
  const [nextMessages, setNextMessages] = useState<any[]>([]);

  useEffect(() => {
    const fetchNextMessages = async () => {
      try {
        const res = await fetch('/api/queue/next');
        const data = await res.json();
        setNextMessages(data.messages || []);
      } catch (error) {
        console.error('Failed to fetch next messages:', error);
      }
    };

    fetchNextMessages();
    // Refetch only when events change (SSE-driven)
  }, [events]);

  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-800 rounded w-1/4"></div>
          <div className="h-20 bg-gray-800 rounded"></div>
        </div>
      </div>
    );
  }

  const priorityColors = {
    urgent: 'bg-red-500/10 text-red-500 border-red-500/30',
    high: 'bg-orange-500/10 text-orange-500 border-orange-500/30',
    normal: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
    low: 'bg-gray-500/10 text-gray-500 border-gray-500/30',
    idle: 'bg-gray-700/10 text-gray-700 border-gray-700/30'
  };

  return (
    <div className="space-y-4">
      {/* Queue Stats */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5 text-blue-500" />
          Queue Status
        </h3>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-2xl font-bold">{data.total_scheduled || 0}</div>
            <div className="text-xs text-gray-500 mt-1">Total Scheduled</div>
          </div>
          
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-500">
              {data.messages_sent_this_hour || 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">Sent This Hour</div>
          </div>
          
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-500">
              {data.active_conversations || 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">Active Conversations</div>
          </div>
        </div>

        {/* Priority Breakdown */}
        {data.by_priority && (
          <div className="mt-4 space-y-2">
            <div className="text-sm text-gray-400 mb-2">Priority Breakdown:</div>
            <div className="grid grid-cols-5 gap-2">
              {Object.entries(data.by_priority).map(([priority, count]: [string, any]) => (
                <div
                  key={priority}
                  className={`px-3 py-2 rounded-lg border text-center ${priorityColors[priority as keyof typeof priorityColors]}`}
                >
                  <div className="text-lg font-bold">{count}</div>
                  <div className="text-xs uppercase mt-1">{priority}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Next Send Time */}
        {data.next_send_time && (
          <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-center gap-2">
            <ArrowRight className="w-4 h-4 text-blue-500" />
            <span className="text-sm">
              Next send: <span className="font-mono text-blue-500">
                {new Date(data.next_send_time).toLocaleTimeString()}
              </span>
            </span>
          </div>
        )}
      </div>

      {/* Next Scheduled Messages */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-cyan-500" />
          Next Scheduled Messages
        </h3>

        {nextMessages.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <AlertTriangle className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <div className="text-sm">No messages scheduled</div>
          </div>
        ) : (
          <div className="space-y-2">
            {nextMessages.map((msg, index) => {
              const secondsUntil = msg.seconds_until_send;
              const isOverdue = secondsUntil < 0;
              const minutesUntil = Math.abs(secondsUntil / 60);

              return (
                <div
                  key={msg.message_id}
                  className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:bg-gray-800 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="text-lg font-bold text-gray-600">
                        #{index + 1}
                      </div>
                      
                      <div className={`px-2 py-1 rounded text-xs border ${
                        priorityColors[msg.priority as keyof typeof priorityColors]
                      }`}>
                        {msg.priority.toUpperCase()}
                      </div>
                      
                      <div className="text-sm text-gray-400">
                        {msg.conversation_id.slice(0, 8)}...
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-xs text-gray-500">Send in</div>
                        <div className={`text-sm font-mono ${
                          isOverdue ? 'text-red-500' : 
                          minutesUntil < 1 ? 'text-green-500' : 'text-gray-300'
                        }`}>
                          {isOverdue ? 'OVERDUE' : 
                           minutesUntil < 1 ? `${Math.ceil(secondsUntil)}s` :
                           `${minutesUntil.toFixed(1)}m`}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-xs text-gray-500">Confidence</div>
                        <div className="text-sm font-semibold text-cyan-500">
                          {(msg.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent Events */}
      {events && events.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Events</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {events.slice(-10).reverse().map((event, index) => (
              <div
                key={index}
                className="text-xs font-mono text-gray-500 py-1 border-b border-gray-800/50 last:border-0"
              >
                <span className="text-gray-600">{new Date(event.timestamp).toLocaleTimeString()}</span>
                {' '}
                <span className={
                  event.type === 'cascade_triggered' ? 'text-yellow-500' :
                  event.type === 'message_sent' ? 'text-green-500' :
                  event.type === 'state_changed' ? 'text-blue-500' :
                  'text-gray-400'
                }>
                  {event.type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


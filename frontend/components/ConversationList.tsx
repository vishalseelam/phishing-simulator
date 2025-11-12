"use client";

import { useState, useEffect } from 'react';
import { MessageSquare, TrendingUp, AlertCircle } from 'lucide-react';

export default function ConversationList() {
  const [conversations, setConversations] = useState<any[]>([]);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const res = await fetch('/api/admin/conversations');
        const data = await res.json();
        setConversations(data || []);
      } catch (error) {
        console.error('Failed to fetch conversations:', error);
      }
    };

    fetchConversations();
    // No polling - will refetch when conversation_updated event arrives
  }, []);

  const stateColors = {
    initiated: 'bg-gray-700 text-gray-400',
    active: 'bg-green-500/10 text-green-500 border-green-500/30',
    engaged: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
    stalled: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30',
    completed: 'bg-gray-600 text-gray-500',
    abandoned: 'bg-red-500/10 text-red-500 border-red-500/30'
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-purple-500" />
        Active Conversations
      </h3>

      {conversations.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <div className="text-sm">No active conversations</div>
        </div>
      ) : (
        <div className="space-y-3">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="font-semibold text-sm">{conv.recipient_name || 'Unknown'}</div>
                  <div className="text-xs text-gray-500 font-mono">{conv.phone_number}</div>
                </div>
                
                <div className={`px-2 py-1 rounded text-xs border ${
                  stateColors[conv.state as keyof typeof stateColors] || stateColors.initiated
                }`}>
                  {conv.state.toUpperCase()}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 mt-3 text-xs">
                <div>
                  <div className="text-gray-500">Messages</div>
                  <div className="font-semibold">{conv.message_count || 0}</div>
                </div>
                <div>
                  <div className="text-gray-500">Replies</div>
                  <div className="font-semibold text-green-500">{conv.reply_count || 0}</div>
                </div>
                <div>
                  <div className="text-gray-500">Sentiment</div>
                  <div className="font-semibold capitalize">
                    {conv.sentiment || 'neutral'}
                  </div>
                </div>
              </div>

              {conv.last_activity_at && (
                <div className="mt-3 text-xs text-gray-500">
                  Last activity: {new Date(conv.last_activity_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


"use client";

import { Clock, ArrowRight, Zap } from 'lucide-react';
import { useState, useEffect } from 'react';

interface Message {
  id: string;
  phone_number: string;
  content: string;
  scheduled_time: string;
  priority: string;
  conversation_id: string;
  status: string;
}

interface MessageQueueProps {
  data: Message[];
  onSelectConversation: (convId: string) => void;
}

export default function MessageQueue({ data, onSelectConversation }: MessageQueueProps) {
  const [currentSimTime, setCurrentSimTime] = useState(new Date());

  // Fetch simulation time every second
  useEffect(() => {
    const fetchTime = async () => {
      try {
        const res = await fetch('/api/time/current');
        const data = await res.json();
        setCurrentSimTime(new Date(data.current_time));
      } catch (error) {
        console.error('Failed to fetch time:', error);
      }
    };
    
    fetchTime();
    const interval = setInterval(fetchTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Make scrollable
  useEffect(() => {
    // Ensure parent has proper height
    const container = document.querySelector('.message-queue-container');
    if (container) {
      container.classList.add('overflow-y-auto', 'h-full');
    }
  }, []);

  // Sort by scheduled time
  const sortedMessages = [...data].sort((a, b) => 
    new Date(a.scheduled_time).getTime() - new Date(b.scheduled_time).getTime()
  );

  const getSecondsUntil = (scheduledTime: string, currentSimTime: Date) => {
    return Math.floor((new Date(scheduledTime).getTime() - currentSimTime.getTime()) / 1000);
  };

  const formatTime = (scheduledTime: string) => {
    const date = new Date(scheduledTime);
    const now = new Date();
    
    // Calculate difference in days
    const diffDays = Math.floor((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    
    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    if (diffDays === 0) {
      return timeStr;
    } else if (diffDays === 1) {
      return 'Tomorrow ' + timeStr;
    } else if (diffDays > 1) {
      return `+${diffDays}d ${timeStr}`;
    } else {
      return date.toLocaleDateString() + ' ' + timeStr;
    }
  };

  const priorityColors = {
    urgent: 'border-l-4 border-l-red-500 bg-red-500/5',
    high: 'border-l-4 border-l-orange-500 bg-orange-500/5',
    normal: 'border-l-4 border-l-blue-500 bg-blue-500/5',
    low: 'border-l-4 border-l-gray-500 bg-gray-500/5',
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-2 message-queue-container min-h-0">
      {sortedMessages.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No messages scheduled</p>
          <p className="text-xs text-gray-700 mt-1">Create a campaign to get started</p>
        </div>
      ) : (
        sortedMessages.map((msg, index) => {
          const secondsUntil = getSecondsUntil(msg.scheduled_time, currentSimTime);
          const isOverdue = secondsUntil < 0;
          const isNext = index === 0 && secondsUntil > 0;

          return (
            <div
              key={msg.id}
              className={`
                p-3 rounded-lg cursor-pointer transition-all hover:bg-gray-800/50
                ${priorityColors[msg.priority as keyof typeof priorityColors] || priorityColors.normal}
                ${isNext ? 'ring-2 ring-cyan-500/50' : ''}
              `}
              onClick={() => onSelectConversation(msg.conversation_id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  {isNext && <Zap className="w-3 h-3 text-cyan-500 animate-pulse" />}
                  <span className="text-xs font-mono text-gray-500">#{index + 1}</span>
                  <span className="text-sm font-semibold">{msg.phone_number}</span>
                </div>
                
                <div className={`text-xs px-2 py-1 rounded ${
                  msg.priority === 'urgent' ? 'bg-red-500/20 text-red-400' :
                  msg.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                  msg.priority === 'normal' ? 'bg-blue-500/20 text-blue-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {msg.priority ? msg.priority.toUpperCase() : 'NORMAL'}
                </div>
              </div>

              {/* Message Content */}
              <p className="text-xs text-gray-400 mb-2 line-clamp-2">
                {msg.content}
              </p>

              {/* Time Info */}
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1 text-gray-500">
                  <Clock className="w-3 h-3" />
                  <span>{formatTime(msg.scheduled_time)}</span>
                </div>
                
                <div className={`font-mono font-semibold text-xs ${
                  isOverdue ? 'text-red-500' :
                  secondsUntil < 60 ? 'text-green-500' :
                  secondsUntil < 300 ? 'text-yellow-500' :
                  'text-gray-500'
                }`}>
                  {isOverdue ? 'READY' :
                   secondsUntil < 60 ? `${secondsUntil}s` :
                   secondsUntil < 3600 ? `${Math.floor(secondsUntil / 60)}m` :
                   `${Math.floor(secondsUntil / 3600)}h ${Math.floor((secondsUntil % 3600) / 60)}m`
                  }
                </div>
              </div>

              {isNext && (
                <div className="mt-2 pt-2 border-t border-cyan-500/20">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1 text-xs text-cyan-500">
                      <ArrowRight className="w-3 h-3" />
                      <span>Next to send</span>
                    </div>
                    
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          const res = await fetch('/api/time/skip_to_next', { method: 'POST' });
                          const data = await res.json();
                          
                          if (data.success) {
                            // Trigger refresh
                            window.dispatchEvent(new CustomEvent('time-jumped'));
                          } else {
                            alert(data.error || 'Failed to skip');
                          }
                        } catch (error) {
                          console.error('Skip failed:', error);
                          alert('Skip failed');
                        }
                      }}
                      className="text-xs px-2 py-1 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 rounded transition-colors"
                    >
                      Jump & Send
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}


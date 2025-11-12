"use client";

import { useState, useEffect, useRef } from 'react';
import { User, Send, Phone, X } from 'lucide-react';

interface Conversation {
  id: string;
  phone_number: string;
  messages: any[];
  state: string;
}

interface EmployeeSimulatorProps {
  conversations: Conversation[];
  selectedEmployee: string | null;
  onSelectEmployee: (id: string | null) => void;
  refreshTrigger?: number; // NEW: Trigger refetch when this changes
}

export default function EmployeeSimulator({
  conversations,
  selectedEmployee,
  onSelectEmployee,
  refreshTrigger
}: EmployeeSimulatorProps) {
  const [tabs, setTabs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [replyInput, setReplyInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedEmployee && !tabs.includes(selectedEmployee)) {
      setTabs(prev => [...prev, selectedEmployee]);
      setActiveTab(selectedEmployee);
    }
  }, [selectedEmployee, tabs]);

  useEffect(() => {
    if (activeTab) {
      fetchMessages(activeTab);
    }
  }, [activeTab]);

  // NEW: Refetch when refreshTrigger changes
  useEffect(() => {
    if (activeTab && refreshTrigger) {
      fetchMessages(activeTab);
    }
  }, [refreshTrigger, activeTab]);

  const fetchMessages = async (conversationId: string) => {
    try {
      const res = await fetch(`/api/employee/conversation/${conversationId}/messages`);
      if (!res.ok) {
        setMessages([]);
        return;
      }
      const data = await res.json();
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      setMessages([]);
    }
  };

  const handleSendReply = async () => {
    if (!replyInput.trim() || !activeTab) return;

    try {
      await fetch('/api/employee/reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeTab,
          message: replyInput
        })
      });

      setReplyInput('');
      fetchMessages(activeTab);
    } catch (error) {
      console.error('Failed to send reply:', error);
    }
  };

  const closeTab = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setTabs(prev => prev.filter(id => id !== convId));
    if (activeTab === convId) {
      setActiveTab(tabs[tabs.indexOf(convId) - 1] || tabs[0] || null);
    }
  };

  const getPhoneNumber = (convId: string) => {
    const conv = conversations.find(c => c.id === convId);
    return conv?.phone_number || 'Unknown';
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tabs */}
      {tabs.length > 0 && (
        <div className="flex items-center gap-1 px-2 py-2 border-b border-gray-800 bg-black/30 overflow-x-auto">
          {tabs.map(convId => (
            <button
              key={convId}
              onClick={() => setActiveTab(convId)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors
                ${activeTab === convId 
                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' 
                  : 'bg-gray-800/50 text-gray-500 hover:bg-gray-800'
                }
              `}
            >
              <Phone className="w-3 h-3" />
              <span className="font-mono">{getPhoneNumber(convId).slice(-4)}</span>
              <X 
                className="w-3 h-3 hover:text-red-500"
                onClick={(e) => closeTab(convId, e)}
              />
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {!activeTab ? (
        <div className="flex-1 flex items-center justify-center text-gray-600">
          <div className="text-center">
            <User className="w-16 h-16 mx-auto mb-4 opacity-30" />
            <p className="text-sm">Select a conversation from the queue</p>
            <p className="text-xs text-gray-700 mt-2">or wait for messages to be scheduled</p>
          </div>
        </div>
      ) : (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
            {messages.length === 0 ? (
              <div className="text-center text-gray-600 py-8">
                <p className="text-sm">No messages yet</p>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={msg.id || index}
                  className={`flex ${msg.sender === 'agent' ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 ${
                      msg.sender === 'agent'
                        ? 'bg-gray-800 text-gray-100 border border-gray-700'
                        : 'bg-purple-600 text-white'
                    }`}
                  >
                    <div className="text-xs text-gray-400 mb-1">
                      {msg.sender === 'agent' ? 'System' : 'Employee'}
                    </div>
                    <div className="text-sm">{msg.content}</div>
                    <div className="text-xs text-gray-500 mt-2">
                      {msg.status === 'scheduled' ? 'Scheduled' : (msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : '')}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Reply Input */}
          <div className="border-t border-gray-800 p-4 bg-black/30">
            <div className="flex gap-2">
              <input
                type="text"
                value={replyInput}
                onChange={(e) => setReplyInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendReply()}
                placeholder="Type employee reply..."
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={handleSendReply}
                disabled={!replyInput.trim()}
                className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:cursor-not-allowed px-4 py-2 rounded-lg transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              Simulate employee response (triggers CASCADE)
            </p>
          </div>
        </>
      )}
    </div>
  );
}


"use client";

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface Message {
  role: 'admin' | 'agent';
  content: string;
  timestamp: string;
}

interface AdminChatProps {
  onUpdate?: () => void;
}

export default function AdminChat({ onUpdate }: AdminChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    
    // Load chat history from localStorage
    const savedHistory = localStorage.getItem('admin_chat_history');
    if (savedHistory) {
      try {
        setMessages(JSON.parse(savedHistory));
      } catch (e) {
        // If parse fails, set initial message
        setMessages([{
          role: 'agent',
          content: 'Hello! I\'m the GhostEye admin agent. You can:\n• Create campaigns\n• Inject messages\n• View status\n• Import history\n\nWhat would you like to do?',
          timestamp: new Date().toISOString()
        }]);
      }
    } else {
      // Set initial message
      setMessages([{
        role: 'agent',
        content: 'Hello! I\'m the GhostEye admin agent. You can:\n• Create campaigns\n• Inject messages\n• View status\n• Import history\n\nWhat would you like to do?',
        timestamp: new Date().toISOString()
      }]);
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  useEffect(() => {
    if (mounted) {
      scrollToBottom();
    }
  }, [messages, mounted]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'admin',
      content: input,
      timestamp: new Date().toISOString()
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    
    // Save to localStorage
    localStorage.setItem('admin_chat_history', JSON.stringify(newMessages));
    
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/admin/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input })
      });

      const data = await response.json();

      const agentMessage: Message = {
        role: 'agent',
        content: data.message || data.data?.message || 'Command executed successfully.',
        timestamp: new Date().toISOString()
      };

      const updatedMessages = [...newMessages, agentMessage];
      setMessages(updatedMessages);
      
      // Save to localStorage
      localStorage.setItem('admin_chat_history', JSON.stringify(updatedMessages));
      
      // Notify parent to refresh
      if (onUpdate) {
        onUpdate();
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      
      const errorMessage: Message = {
        role: 'agent',
        content: '❌ Failed to process command. Please try again.',
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'admin' ? 'justify-end' : 'justify-start'} animate-fadeIn`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === 'admin'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-100 border border-gray-700'
              }`}
            >
              <div className="text-xs text-gray-400 mb-1">
                {message.role === 'admin' ? 'You' : 'Agent'}
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {message.content}
              </div>
              <div className="text-xs text-gray-500 mt-2">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start animate-fadeIn">
            <div className="bg-gray-800 border border-gray-700 rounded-2xl px-4 py-3">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a command... (e.g., 'Create phishing campaign about password reset')"
            disabled={isLoading}
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed px-6 py-3 rounded-lg transition-colors flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            <span className="text-sm font-medium">Send</span>
          </button>
        </div>
        
        <div className="mt-2 text-xs text-gray-500">
          Try: "Start phishing about password reset" or "Show queue status"
        </div>
      </div>
    </div>
  );
}


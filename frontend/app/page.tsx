"use client";

import { useState, useEffect } from 'react';
import AdminChat from '@/components/AdminChat';
import MessageQueue from '@/components/MessageQueue';
import EmployeeSimulator from '@/components/EmployeeSimulator';
import { MessageSquare, Clock, Users, RotateCcw } from 'lucide-react';
import TimeControl from '@/components/TimeControl';

export default function Home() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<string | null>(null);
  const [queueData, setQueueData] = useState<any[]>([]);
  const [isResetting, setIsResetting] = useState(false);
  const [messageRefreshTrigger, setMessageRefreshTrigger] = useState(0); // NEW: Trigger for EmployeeSimulator

  // WebSocket connection
  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: NodeJS.Timeout;
    
    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        console.log('[WS] Connected');
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[WS] Event:', data.type);
          
          // Fetch when events happen
          switch (data.type) {
            case 'queue_updated':
            case 'message_scheduled':
            case 'campaign_scheduled':  // NEW
            case 'cascade_triggered':
            case 'message_sent':  // NEW - Also refresh messages
            case 'time_changed':  // NEW
              fetchQueue();
              fetchConversations();
              setMessageRefreshTrigger(prev => prev + 1); // NEW: Trigger message refetch
              break;
            case 'conversation_updated':
            case 'employee_replied':
              fetchConversations();
              setMessageRefreshTrigger(prev => prev + 1); // NEW: Trigger message refetch
              break;
          }
        } catch (error) {
          console.error('[WS] Parse error:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
      };
      
      ws.onclose = () => {
        console.log('[WS] Disconnected, reconnecting in 3s...');
        // Reconnect after 3 seconds
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };
    
    connect();
    
    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  const fetchQueue = async () => {
    try {
      const res = await fetch('/api/queue/all');
      const data = await res.json();
      setQueueData(data.messages || []);
    } catch (error) {
      console.error('Failed to fetch queue:', error);
    }
  };

  const fetchConversations = async () => {
    try {
      const res = await fetch('/api/conversations/all');
      if (!res.ok) {
        setConversations([]);
        return;
      }
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
      setConversations([]);
    }
  };

  // Fetch initial data once only
  useEffect(() => {
    fetchQueue();
    fetchConversations();
  }, []); // Empty dependency - run once only
  
  // Listen for time jump events
  useEffect(() => {
    const handleTimeJump = () => {
      fetchQueue();
      fetchConversations();
      setMessageRefreshTrigger(prev => prev + 1); // NEW: Trigger message refetch
    };
    
    window.addEventListener('time-jumped', handleTimeJump);
    return () => window.removeEventListener('time-jumped', handleTimeJump);
  }, []);

  const handleReset = async () => {
    if (!confirm('⚠️ Reset everything? This will delete all campaigns, conversations, and messages.')) {
      return;
    }

    setIsResetting(true);
    try {
      await fetch('/api/admin/reset', { method: 'POST' });
      
      // Clear local state
      setQueueData([]);
      setConversations([]);
      setSelectedEmployee(null);
      
      // Clear chat history from localStorage
      localStorage.removeItem('admin_chat_history');
      
      // Reload page to reset everything
      window.location.reload();
    } catch (error) {
      console.error('Reset failed:', error);
      alert('❌ Reset failed. Check console.');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="h-screen bg-[#0a0a0a] text-gray-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-black/50 backdrop-blur px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-500 to-cyan-500 bg-clip-text text-transparent">
              GhostEye v2
            </h1>
            <p className="text-sm text-gray-500 mt-1">Multi-Conversation Phishing Orchestrator</p>
          </div>
          
          <div className="flex items-center gap-6">
            {/* Time Control */}
            <TimeControl />
            
            <div className="h-6 w-px bg-gray-700" />
            
            <div className="flex items-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-blue-500" />
                <span className="text-gray-400">{conversations.length} Conversations</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-500" />
                <span className="text-gray-400">{queueData.length} Scheduled</span>
              </div>
            </div>
            
            <button
              onClick={handleReset}
              disabled={isResetting}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-lg text-red-500 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className={`w-4 h-4 ${isResetting ? 'animate-spin' : ''}`} />
              <span>Reset All</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Layout: 3 Panels */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden min-h-0">
        {/* LEFT PANEL: Message Queue (Time-Sorted) */}
        <div className="col-span-3 border-r border-gray-800 flex flex-col bg-[#0f0f0f] min-h-0">
          <div className="px-4 py-3 border-b border-gray-800 bg-black/30 flex-shrink-0">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <Clock className="w-4 h-4 text-cyan-500" />
              Message Queue (Time Sorted)
            </h2>
            <p className="text-xs text-gray-500 mt-1">All scheduled messages</p>
          </div>
          
          <MessageQueue 
            data={queueData}
            onSelectConversation={(convId) => setSelectedEmployee(convId)}
          />
        </div>

        {/* CENTER PANEL: Admin Chat */}
        <div className="col-span-5 flex flex-col bg-[#0a0a0a] min-h-0">
          <div className="px-4 py-3 border-b border-gray-800 bg-black/30 flex-shrink-0">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-blue-500" />
              Admin Control
            </h2>
            <p className="text-xs text-gray-500 mt-1">Command center</p>
          </div>
          
          <AdminChat onUpdate={() => {
            fetchQueue();
            fetchConversations();
          }} />
        </div>

        {/* RIGHT PANEL: Employee Simulator */}
        <div className="col-span-4 border-l border-gray-800 flex flex-col bg-[#0f0f0f] min-h-0">
          <div className="px-4 py-3 border-b border-gray-800 bg-black/30 flex-shrink-0">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <Users className="w-4 h-4 text-purple-500" />
              Employee Simulator
            </h2>
            <p className="text-xs text-gray-500 mt-1">Test employee responses</p>
          </div>
          
          <EmployeeSimulator 
            conversations={conversations}
            selectedEmployee={selectedEmployee}
            onSelectEmployee={setSelectedEmployee}
            refreshTrigger={messageRefreshTrigger}
          />
        </div>
      </div>
    </div>
  );
}

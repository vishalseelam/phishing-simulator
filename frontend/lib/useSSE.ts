import { useState, useEffect, useRef } from 'react';

interface SSEEvent {
  type: string;
  data: any;
  timestamp: string;
}

export function useSSE(url: string) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Create EventSource connection
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('[SSE] Connected');
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[SSE] Event received:', data.type);
        
        setEvents((prev) => {
          // Keep last 100 events
          const newEvents = [...prev, data];
          return newEvents.slice(-100);
        });
      } catch (error) {
        console.error('[SSE] Failed to parse event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Error:', error);
      setIsConnected(false);
      
      // Reconnect after 5 seconds
      setTimeout(() => {
        console.log('[SSE] Reconnecting...');
        eventSource.close();
      }, 5000);
    };

    // Cleanup on unmount
    return () => {
      console.log('[SSE] Disconnecting');
      eventSource.close();
    };
  }, [url]);

  return { events, isConnected };
}


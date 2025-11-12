"use client";

import { useState, useEffect } from 'react';
import { Clock, FastForward, SkipForward, Play } from 'lucide-react';

export default function TimeControl() {
  const [currentTime, setCurrentTime] = useState<Date | null>(null);
  const [isSimulation, setIsSimulation] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    
    // Fetch current time
    const fetchTime = async () => {
      try {
        const res = await fetch('/api/time/current');
        const data = await res.json();
        setCurrentTime(new Date(data.current_time));
        setIsSimulation(data.is_simulation);
      } catch (error) {
        console.error('Failed to fetch time:', error);
      }
    };

    fetchTime();
    const interval = setInterval(fetchTime, 1000);
    return () => clearInterval(interval);
  }, []);
  
  if (!mounted || !currentTime) {
    return <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
      <Clock className="w-4 h-4 text-gray-500 animate-pulse" />
      <span className="font-mono text-sm text-gray-500">Loading...</span>
    </div>;
  }

  const skipToNext = async () => {
    try {
      const res = await fetch('/api/time/skip_to_next', { method: 'POST' });
      const data = await res.json();
      
      if (data.success) {
        setCurrentTime(new Date(data.skipped_to));
        // Trigger page refresh via event
        window.dispatchEvent(new CustomEvent('time-jumped'));
      } else {
        alert(data.error || 'No messages to skip to');
      }
    } catch (error) {
      console.error('Skip failed:', error);
      alert('Skip failed. Check console.');
    }
  };

  const fastForward = async (minutes: number) => {
    try {
      const res = await fetch(`/api/time/fast_forward?minutes=${minutes}`, { method: 'POST' });
      const data = await res.json();
      
      if (data.success) {
        setCurrentTime(new Date(data.new_time));
        // Trigger page refresh via event
        window.dispatchEvent(new CustomEvent('time-jumped'));
      }
    } catch (error) {
      console.error('Fast forward failed:', error);
      alert('Fast forward failed. Check console.');
    }
  };

  return (
    <div className="flex items-center gap-3">
      {/* Current Time */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
        <Clock className="w-4 h-4 text-cyan-500" />
        <span className="font-mono text-sm font-semibold">
          {currentTime.toLocaleTimeString()}
        </span>
        {isSimulation && (
          <span className="text-xs px-1.5 py-0.5 bg-cyan-500/20 text-cyan-400 rounded">
            SIM
          </span>
        )}
      </div>

      {/* Time Controls */}
      {isSimulation && (
        <>
          <button
            onClick={skipToNext}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-lg text-cyan-400 text-xs transition-colors"
          >
            <SkipForward className="w-3.5 h-3.5" />
            Skip to Next
          </button>

          <button
            onClick={() => fastForward(60)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 rounded-lg text-blue-400 text-xs transition-colors"
          >
            <FastForward className="w-3.5 h-3.5" />
            +1 Hour
          </button>

          <button
            onClick={() => fastForward(15)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 rounded-lg text-blue-400 text-xs transition-colors"
          >
            +15m
          </button>
        </>
      )}
    </div>
  );
}


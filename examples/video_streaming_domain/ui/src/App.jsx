import React, { useState, useEffect } from 'react';
import { Play, Pause, Activity, Server, Zap } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

// --- Components ---

const VideoCard = ({ video, onPlay }) => (
  <div className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:scale-105 transition-transform cursor-pointer" onClick={() => onPlay(video)}>
    <img src={video.thumbnail_url} alt={video.title} className="w-full h-48 object-cover" />
    <div className="p-4">
      <h3 className="text-lg font-bold text-white">{video.title}</h3>
      <p className="text-gray-400 text-sm mt-1">{video.category} • {Math.floor(video.duration_seconds / 60)} min</p>
    </div>
  </div>
);

const VideoPlayer = ({ video, onClose }) => {
  if (!video) return null;

  return (
    <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-xl w-full max-w-4xl overflow-hidden relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-white hover:text-red-500 z-10">
          Close
        </button>
        <video
          src={video.stream_url}
          controls
          autoPlay
          className="w-full aspect-video bg-black"
        />
        <div className="p-6">
          <h2 className="text-2xl font-bold text-white">{video.title}</h2>
          <p className="text-gray-300 mt-2">{video.description}</p>
        </div>
      </div>
    </div>
  );
};

const OpsDashboard = ({ metrics }) => {
  const activePods = new Set(metrics.podHistory.map(m => m.podName)).size;

  return (
    <div className="bg-gray-900 border-l border-gray-800 w-96 p-6 flex flex-col h-screen fixed right-0 top-0 overflow-y-auto">
      <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
        <Activity className="text-blue-500" /> System Status
      </h2>

      {/* Active Replicas */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-400">Active Replicas</span>
          <Server className="text-green-500" size={20} />
        </div>
        <div className="text-3xl font-bold text-white">{activePods}</div>
        <div className="text-xs text-gray-500 mt-1">Unique pods responding</div>
      </div>

      {/* Request Latency Chart */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6 h-64">
        <h3 className="text-gray-400 text-sm mb-4">Response Latency (ms)</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={metrics.latencyHistory.slice(-20)}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="time" hide />
            <YAxis stroke="#9CA3AF" fontSize={12} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
              itemStyle={{ color: '#60A5FA' }}
            />
            <Line type="monotone" dataKey="latency" stroke="#3B82F6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Active Pod List */}
      <div className="bg-gray-800 rounded-lg p-4 flex-1">
        <h3 className="text-gray-400 text-sm mb-4">Active Pods</h3>
        <div className="space-y-2">
          {Array.from(new Set(metrics.podHistory.map(m => m.podName))).map(pod => (
            <div key={pod} className="flex items-center gap-2 text-sm text-gray-300 bg-gray-700/50 p-2 rounded">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              {pod}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const LoadGenerator = ({ onGenerateLoad, isGenerating }) => (
  <button
    onClick={onGenerateLoad}
    disabled={isGenerating}
    className={`fixed bottom-8 right-[400px] flex items-center gap-2 px-6 py-3 rounded-full font-bold shadow-lg transition-all ${
      isGenerating
        ? 'bg-red-600 text-white animate-pulse cursor-not-allowed'
        : 'bg-blue-600 hover:bg-blue-500 text-white hover:scale-105'
    }`}
  >
    <Zap size={20} />
    {isGenerating ? 'Generating Load...' : 'Simulate High Traffic'}
  </button>
);

// --- Main App ---

function App() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [metrics, setMetrics] = useState({
    podHistory: [],
    latencyHistory: []
  });
  const [isGeneratingLoad, setIsGeneratingLoad] = useState(false);

  // Fetch Catalog
  useEffect(() => {
    fetch('/api/catalog/videos')
      .then(res => res.json())
      .then(setVideos)
      .catch(console.error);
  }, []);

  // Background Health Check / Metrics Polling
  useEffect(() => {
    const poll = async () => {
      const start = performance.now();
      try {
        const res = await fetch('/api/stream/health');
        const end = performance.now();
        const latency = Math.round(end - start);
        const podName = res.headers.get('X-Pod-Name') || 'unknown';

        setMetrics(prev => ({
          podHistory: [...prev.podHistory, { time: Date.now(), podName }].slice(-50),
          latencyHistory: [...prev.latencyHistory, { time: Date.now(), latency }].slice(-50)
        }));
      } catch (e) {
        console.error("Health check failed", e);
      }
    };

    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerateLoad = async () => {
    setIsGeneratingLoad(true);
    // Fire 100 concurrent requests
    const requests = Array(100).fill(0).map(() => fetch('/api/stream/health'));
    await Promise.all(requests);
    setTimeout(() => setIsGeneratingLoad(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      {/* Main Content */}
      <div className="flex-1 p-8 pr-[400px]">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-600">
            MMF Stream
          </h1>
          <p className="text-gray-400 mt-2">Microservices Scaling Demo</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {videos.map(video => (
            <VideoCard key={video.id} video={video} onPlay={setSelectedVideo} />
          ))}
        </div>
      </div>

      {/* Sidebar Dashboard */}
      <OpsDashboard metrics={metrics} />

      {/* Load Generator Button */}
      <LoadGenerator onGenerateLoad={handleGenerateLoad} isGenerating={isGeneratingLoad} />

      {/* Video Player Modal */}
      {selectedVideo && (
        <VideoPlayer video={selectedVideo} onClose={() => setSelectedVideo(null)} />
      )}
    </div>
  );
}

export default App;

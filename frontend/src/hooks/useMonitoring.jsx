import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, sessionSocketUrl } from "../lib/api.js";
import { BehaviorTracker } from "../lib/tracker.js";

const MonitoringContext = createContext(null);

export function MonitoringProvider({ children }) {
  const [info, setInfo] = useState(null);
  const [backendError, setBackendError] = useState(null);
  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [liveSeries, setLiveSeries] = useState([]);
  const [estimate, setEstimate] = useState(null);
  const [wsState, setWsState] = useState("closed");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);              // bumps on every live update so pages can refetch
  const [selectedSessionId, setSelectedSessionId] = useState(null);

  const trackerRef = useRef(null);
  const socketRef = useRef(null);
  const sessionRef = useRef(null);
  const retryRef = useRef(null);
  const previewTimer = useRef(null);

  useEffect(() => {
    api.modelInfo().then(setInfo).catch((e) => setBackendError(e.message));
  }, []);

  const closeSocket = useCallback(() => {
    clearTimeout(retryRef.current);
    if (socketRef.current) {
      socketRef.current.onclose = null;
      socketRef.current.close();
      socketRef.current = null;
    }
    setWsState("closed");
  }, []);

  const openSocket = useCallback((id) => {
    const socket = new WebSocket(sessionSocketUrl(id));
    socketRef.current = socket;
    setWsState("connecting");
    socket.onopen = () => setWsState("open");
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "update") {
        setLiveSeries((previous) => [...previous, message.metric]);
        setEstimate(message.estimate);
        setTick((t) => t + 1);
      } else if (message.type === "error") {
        setError(message.detail);
      }
    };
    socket.onclose = () => {
      setWsState("closed");
      if (sessionRef.current === id) {
        retryRef.current = setTimeout(() => {
          if (sessionRef.current === id) openSocket(id);
        }, 3000);
      }
    };
  }, []);

  const sendMinute = useCallback(async (minute) => {
    const id = sessionRef.current;
    if (!id) return;
    const socket = socketRef.current;
    try {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "metrics", data: minute }));
      } else {
        const result = await api.postMetrics(id, minute);   // REST fallback if the socket is down
        setLiveSeries((previous) => [...previous, result.metric]);
        setEstimate(result.estimate);
        setTick((t) => t + 1);
      }
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const started = await api.startSession(info.consent_version);
      sessionRef.current = started.session_id;
      setSessionId(started.session_id);
      setSelectedSessionId(started.session_id);
      setLiveSeries([]);
      setEstimate(null);
      setRunning(true);
      openSocket(started.session_id);
      const tracker = new BehaviorTracker(sendMinute);
      trackerRef.current = tracker;
      tracker.start();
      previewTimer.current = setInterval(() => setPreview(tracker.snapshot()), 1000);
    } catch (e) {
      setError(e.message);
    }
  }, [info, openSocket, sendMinute]);

  const stop = useCallback(async () => {
    const id = sessionRef.current;
    if (trackerRef.current) trackerRef.current.stop();
    trackerRef.current = null;
    clearInterval(previewTimer.current);
    setPreview(null);
    setRunning(false);
    sessionRef.current = null;
    closeSocket();
    if (id) {
      try {
        await api.stopSession(id);
      } catch (e) {
        setError(e.message);
      }
    }
    setTick((t) => t + 1);
  }, [closeSocket]);

  useEffect(() => () => {
    if (trackerRef.current) trackerRef.current.stop();
    clearInterval(previewTimer.current);
    closeSocket();
  }, [closeSocket]);

  const value = useMemo(() => ({
    info, backendError, running, sessionId, liveSeries, estimate, wsState, preview, error, tick,
    selectedSessionId, setSelectedSessionId, start, stop, clearError: () => setError(null),
  }), [info, backendError, running, sessionId, liveSeries, estimate, wsState, preview, error, tick,
    selectedSessionId, start, stop]);

  return <MonitoringContext.Provider value={value}>{children}</MonitoringContext.Provider>;
}

export function useMonitoring() {
  return useContext(MonitoringContext);
}

/** Small data-fetching hook: refetches when deps change. */
export function useFetch(loader, deps) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loader()
      .then((result) => { if (!cancelled) { setData(result); setFetchError(null); } })
      .catch((e) => { if (!cancelled) setFetchError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, loading, error: fetchError };
}

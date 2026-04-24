import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

type InputMode = "webcam" | "upload";

type Detection = {
  face_id: number;
  emotion: string;
  confidence: number;
  message: string;
  suggestion: string;
  wellness_score: number;
  gradcam_base64: string;
};

type PredictResponse = {
  request_id: string;
  detections: Detection[];
  model_metrics: {
    training_accuracy: number;
    validation_accuracy: number;
  };
};

type HistoryRecord = {
  id: number;
  emotion: string;
  confidence: number;
  suggestion: string;
  created_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function classNames(...classes: Array<string | false>): string {
  return classes.filter(Boolean).join(" ");
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

async function toBlob(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<Blob> {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Unable to access canvas context.");
  }
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Failed to capture webcam frame."));
        return;
      }
      resolve(blob);
    }, "image/jpeg");
  });
}

export default function App() {
  const [error, setError] = useState("");
  const [apiBase, setApiBase] = useState<string>(API_BASE);
  const [apiConnected, setApiConnected] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("webcam");
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [predictData, setPredictData] = useState<PredictResponse | null>(null);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [predictLoading, setPredictLoading] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const autoDetectTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const topDetection = predictData?.detections[0] ?? null;
  const modelMetrics = predictData?.model_metrics;
  const calmMode = topDetection ? ["sad", "angry", "fear"].includes(topDetection.emotion.toLowerCase()) : false;

  const weeklySeries = useMemo(() => {
    const now = new Date();
    const labels = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now);
      d.setDate(now.getDate() - (6 - i));
      return d.toLocaleDateString("en-US", { weekday: "short" });
    });
    const scores = labels.map((_, i) => {
      const d = new Date(now);
      d.setDate(now.getDate() - (6 - i));
      const dateKey = d.toISOString().slice(0, 10);
      const dayRecords = history.filter((h) => h.created_at.startsWith(dateKey));
      if (!dayRecords.length) {
        return 0;
      }
      return dayRecords.reduce((acc, cur) => acc + cur.confidence, 0) / dayRecords.length;
    });
    return { labels, scores };
  }, [history]);

  const pathD = useMemo(() => {
    if (weeklySeries.scores.every((s) => s === 0)) {
      return "M 0 90 L 100 90";
    }
    return weeklySeries.scores
      .map((score, index) => {
        const x = (index / 6) * 100;
        const y = 100 - score * 100;
        return `${index === 0 ? "M" : "L"} ${x} ${Math.max(8, y)}`;
      })
      .join(" ");
  }, [weeklySeries.scores]);

  async function enableCamera(): Promise<void> {
    setCameraError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (!videoRef.current) {
        return;
      }
      videoRef.current.srcObject = stream;
      videoRef.current.onloadedmetadata = () => {
        setCameraReady(true);
        void runPrediction({ silent: true });
      };
    } catch {
      setCameraError("Camera access denied. Allow webcam permissions and retry.");
      setCameraReady(false);
    }
  }

  const apiCandidates = useMemo(() => {
    return Array.from(new Set([API_BASE, "http://localhost:8000", "http://127.0.0.1:8000"]));
  }, []);

  async function fetchWithTimeout(url: string, init?: RequestInit, timeoutMs = 7000): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function resolveApiBase(): Promise<void> {
    for (const candidate of apiCandidates) {
      try {
        const res = await fetchWithTimeout(`${candidate}/health`, { method: "GET" }, 1800);
        if (res.ok) {
          setApiBase(candidate);
          setApiConnected(true);
          setError("");
          return;
        }
      } catch {
        // Continue checking remaining candidates.
      }
    }
    setApiConnected(false);
    setError("Cannot connect to backend API. Start FastAPI server on port 8000 and retry.");
  }

  async function loadHistory(): Promise<void> {
    try {
      const response = await fetchWithTimeout(`${apiBase}/history`);
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as { records: HistoryRecord[] };
      setHistory(data.records);
    } catch {
      // History endpoint can be unavailable during frontend-only demo usage.
    }
  }

  useEffect(() => {
    void resolveApiBase();
  }, [apiCandidates]);

  useEffect(() => {
    if (apiConnected) {
      void loadHistory();
    }
  }, [apiConnected, apiBase]);

  async function runPrediction(options?: { silent?: boolean }): Promise<void> {
    if (!apiConnected) {
      if (!options?.silent) {
        setError("Backend API is not connected yet. Please wait or start FastAPI on port 8000.");
      }
      return;
    }
    setPredictLoading(true);
    if (!options?.silent) {
      setError("");
    }
    try {
      const formData = new FormData();
      if (inputMode === "upload") {
        if (!uploadFile) {
          if (!options?.silent) {
            throw new Error("Select an image before running prediction.");
          }
          return;
        }
        formData.append("file", uploadFile);
      } else {
        if (!videoRef.current || !canvasRef.current) {
          if (!options?.silent) {
            throw new Error("Camera stream is not ready.");
          }
          return;
        }
        const frameBlob = await toBlob(videoRef.current, canvasRef.current);
        formData.append("file", frameBlob, "webcam_capture.jpg");
      }
      let response: Response;
      try {
        response = await fetchWithTimeout(`${apiBase}/predict`, {
          method: "POST",
          body: formData,
        });
      } catch {
        throw new Error("Failed to fetch from backend API. Make sure FastAPI is running and CORS is configured.");
      }
      const data = (await response.json()) as PredictResponse & { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? "Prediction failed.");
      }
      setPredictData(data);
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Prediction failed unexpectedly.");
    } finally {
      setPredictLoading(false);
    }
  }

  useEffect(() => {
    if (inputMode !== "upload" || !uploadFile) {
      return;
    }
    void runPrediction();
  }, [uploadFile, inputMode]);

  useEffect(() => {
    if (autoDetectTimerRef.current) {
      clearInterval(autoDetectTimerRef.current);
      autoDetectTimerRef.current = null;
    }
    if (inputMode !== "webcam" || !cameraReady) {
      return;
    }
    autoDetectTimerRef.current = setInterval(() => {
      void runPrediction({ silent: true });
    }, 2800);
    return () => {
      if (autoDetectTimerRef.current) {
        clearInterval(autoDetectTimerRef.current);
      }
    };
  }, [inputMode, cameraReady]);

  return (
    <div
      className={classNames(
        "min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-slate-100 transition-colors duration-700",
        calmMode && "from-teal-950 via-cyan-950 to-slate-900"
      )}
    >
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-10">
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="space-y-4"
        >
          <p className="text-sm uppercase tracking-[0.3em] text-cyan-300">SentiFace</p>
          <h1 className="max-w-3xl text-4xl font-semibold leading-tight text-white md:text-6xl">
            Facial Emotion Recognition with Intelligent Feedback
          </h1>
          <p className="max-w-2xl text-slate-300">
            Real-time CNN inference, GAN enhancement, Grad-CAM explainability, and wellness-aware suggestions in one production-ready workspace.
          </p>
        </motion.section>

        <section className="grid gap-8 lg:grid-cols-[1.2fr_1fr]">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setInputMode("webcam")}
                  className={classNames("px-3 py-2 text-sm ring-1 ring-slate-600", inputMode === "webcam" && "bg-cyan-400 text-slate-900")}
                >
                  Webcam
                </button>
                <button
                  onClick={() => setInputMode("upload")}
                  className={classNames("px-3 py-2 text-sm ring-1 ring-slate-600", inputMode === "upload" && "bg-cyan-400 text-slate-900")}
                >
                  Upload
                </button>
                <p className="px-3 py-2 text-sm text-cyan-200 ring-1 ring-cyan-800">
                  {predictLoading ? "Analyzing..." : "Auto detection is active"}
                </p>
              </div>

              {inputMode === "webcam" ? (
                <div className="space-y-2">
                  <video ref={videoRef} autoPlay muted playsInline className="w-full bg-slate-950 ring-1 ring-slate-700" />
                  <canvas ref={canvasRef} className="hidden" />
                  {!cameraReady ? (
                    <button onClick={enableCamera} className="px-4 py-2 text-sm ring-1 ring-slate-600">
                      Enable Camera
                    </button>
                  ) : (
                    <p className="text-sm text-emerald-300">Camera is active.</p>
                  )}
                  {cameraError && <p className="text-sm text-rose-300">{cameraError}</p>}
                </div>
              ) : (
                <div className="space-y-2">
                  <input
                    type="file"
                    accept="image/png,image/jpg,image/jpeg"
                    onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                    className="w-full text-sm file:mr-4 file:border-0 file:bg-cyan-400 file:px-4 file:py-2 file:font-semibold file:text-slate-900"
                  />
                  <p className="text-sm text-slate-400">Supports single and multi-face images.</p>
                </div>
              )}
              {!apiConnected && <p className="text-sm text-amber-300">Connecting to backend...</p>}
              {error && <p className="text-sm text-rose-300">{error}</p>}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={topDetection?.face_id ?? "empty"}
                initial={{ opacity: 0, x: 25 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -15 }}
                className="space-y-4 bg-slate-900/60 p-6 ring-1 ring-slate-700/70"
              >
                <h2 className="text-xl font-semibold text-white">Emotion Result</h2>
                {!topDetection ? (
                  <p className="text-slate-300">Run prediction to view emotion, confidence, and suggestions.</p>
                ) : (
                  <>
                    <p className="text-3xl font-bold capitalize text-cyan-300">{topDetection.emotion}</p>
                    <div>
                      <div className="mb-1 flex justify-between text-sm text-slate-300">
                        <span>Confidence</span>
                        <span>{formatPct(topDetection.confidence)}</span>
                      </div>
                      <div className="h-2 bg-slate-700">
                        <motion.div
                          className="h-full bg-cyan-400"
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.round(topDetection.confidence * 100)}%` }}
                        />
                      </div>
                    </div>
                    <p className="text-sm text-slate-300">{topDetection.message}</p>
                    <p className="text-sm text-cyan-100">Wellness Tip: {topDetection.suggestion}</p>
                    <p className="text-sm text-teal-200">Wellness Score: {topDetection.wellness_score.toFixed(0)}/100</p>
                    {modelMetrics && (
                      <p className="text-xs text-slate-400">
                        Training Acc: {formatPct(modelMetrics.training_accuracy)} | Validation Acc: {formatPct(modelMetrics.validation_accuracy)}
                      </p>
                    )}
                    {topDetection.gradcam_base64 && (
                      <img
                        src={`data:image/png;base64,${topDetection.gradcam_base64}`}
                        alt="Grad CAM explanation"
                        className="w-full ring-1 ring-slate-700"
                      />
                    )}
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          </section>

        <section className="grid gap-8 lg:grid-cols-2">
            <div className="space-y-3 bg-slate-900/60 p-6 ring-1 ring-slate-700/70">
              <h3 className="text-lg font-semibold">Emotion Trend (7 days)</h3>
              <svg viewBox="0 0 100 100" className="h-48 w-full bg-slate-950/70 p-2">
                <path d={pathD} fill="none" stroke="#22d3ee" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              </svg>
              <div className="grid grid-cols-7 gap-2 text-center text-xs text-slate-400">
                {weeklySeries.labels.map((label) => (
                  <span key={label}>{label}</span>
                ))}
              </div>
            </div>
            <div className="space-y-3 bg-slate-900/60 p-6 ring-1 ring-slate-700/70">
              <h3 className="text-lg font-semibold">Detected Faces</h3>
              <div className="space-y-2 text-sm">
                {(predictData?.detections ?? []).map((det) => (
                  <div key={det.face_id} className="flex items-center justify-between border-b border-slate-700 pb-2">
                    <span>Face #{det.face_id}</span>
                    <span className="capitalize text-cyan-300">
                      {det.emotion} ({formatPct(det.confidence)})
                    </span>
                  </div>
                ))}
                {!(predictData?.detections.length ?? 0) && <p className="text-slate-400">No detections yet.</p>}
              </div>
            </div>
          </section>
      </main>
    </div>
  );
}
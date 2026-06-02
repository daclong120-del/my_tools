"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Globe,
  Cpu,
  Layers,
  Activity,
  FileSpreadsheet,
  Play,
  Square,
  RotateCw,
  SlidersHorizontal,
  Plus,
  ArrowUpDown,
  Download,
  AlertCircle,
  CheckCircle,
  X,
  FileDown,
  ExternalLink,
  RefreshCw,
  LogOut,
  ChevronRight,
  Settings,
  FolderOpen
} from "lucide-react";

export default function Home() {
  // Navigation & Screen states
  const [currentTab, setCurrentTab] = useState("setup");
  const [connectionStatus, setConnectionStatus] = useState("disconnected"); // disconnected, connecting, connected, error
  const [connectingText, setConnectingText] = useState("Đang kết nối tới Chrome...");
  const [debugPort, setDebugPort] = useState("9222");
  const [workersCount, setWorkersCount] = useState(4);
  const [errorMessage, setErrorMessage] = useState("");
  const [downloadDir, setDownloadDir] = useState("");
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [isElectron, setIsElectron] = useState(false);

  // Detect Electron environment after mount to avoid hydration mismatch
  useEffect(() => {
    setIsElectron(typeof window !== 'undefined' && !!window.electronAPI);
  }, []);
  
  // Tab Manager States
  const [tabs, setTabs] = useState([]);
  const [isRefreshingTabs, setIsRefreshingTabs] = useState(false);

  // Modal States
  const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
  const [pagesToDownload, setPagesToDownload] = useState(5);
  const [modalTargetType, setModalTargetType] = useState("all"); // "all" or specific tab_id

  // Dashboard / Realtime Download States
  const [isDownloading, setIsDownloading] = useState(false);
  const [activeJobs, setActiveJobs] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    downloading: 0,
    pending: 0,
    done: 0,
    failed: 0,
    duplicate: 0
  });
  const [logs, setLogs] = useState([]);
  const logEndRef = useRef(null);

  const addLog = (type, message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { type, message, timestamp }]);
  };


  // Report & Export States
  const [reportFilters, setReportFilters] = useState({
    platform: "all",
    area: "all",
    appName: "all",
    mediaType: "all"
  });
  const [reportData, setReportData] = useState([]);

  // System Monitor suggestion
  const sysMonitorSuggestion = 4;

  // Dynamic stats calculated from reportData
  const totalSizeMB = reportData.reduce((acc, row) => {
    const parsed = parseFloat(row.size);
    return isNaN(parsed) ? acc : acc + parsed;
  }, 0).toFixed(1);

  const uniquePlatforms = new Set(reportData.map(r => r.platform).filter(Boolean)).size;
  const platformNames = Array.from(new Set(reportData.map(r => r.platform).filter(Boolean))).join(" / ") || "Không có";

  // Auto-scroll logs
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);


  // Load configuration from backend
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/config");
        if (res.ok) {
          const data = await res.json();
          if (data.download_dir) {
            setDownloadDir(data.download_dir);
          }
        }
      } catch (err) {
        console.error("Lỗi lấy cấu hình từ backend:", err);
      }
    };
    loadConfig();
  }, [connectionStatus]);

  // Handle WebSocket connection for real-time progress & logs
  useEffect(() => {
    let ws;
    if (connectionStatus === "connected") {
      ws = new WebSocket("ws://127.0.0.1:8003/api/v1/socialpeta/ws");
      
      ws.onopen = () => {
        addLog("info", "Đã kết nối WebSocket đồng bộ dữ liệu...");
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.stats) {
            setStats({
              total: data.stats.total_sniffed || 0,
              downloading: data.stats.downloading || 0,
              pending: data.stats.pending || 0,
              done: data.stats.done || 0,
              failed: data.stats.failed || 0,
              duplicate: data.stats.duplicate || 0
            });
          }
          
          if (data.tab_states) {
            const newJobs = Object.entries(data.tab_states).map(([id, state]) => ({
              tab_id: parseInt(id),
              url: state.url || "",
              type: (state.title || "").includes("TikTok") ? "TikTok Ads" : (state.title || "").includes("Facebook") ? "Facebook Ads" : "SocialPeta Page",
              progress: state.target_pages > 0 ? Math.round((state.current_page / state.target_pages) * 100) : 0,
              pending: 0,
              downloading: state.status === "running" ? 1 : 0,
              done: state.scraped_count || 0,
              failed: 0,
              status: state.status.toUpperCase()
            }));
            setActiveJobs(newJobs);
            
            const running = Object.values(data.tab_states).some(job => job.status === "running");
            setIsDownloading(running);

            setTabs(prev => prev.map(t => {
              const state = data.tab_states[t.tab_id.toString()];
              if (state) {
                return {
                  ...t,
                  status: state.status.toUpperCase(),
                  page: `Trang ${state.current_page}/${state.target_pages}`
                };
              }
              return t;
            }));
          }
          
          if (data.logs && data.logs.length > 0) {
            setLogs(prev => {
              const newLogs = [...prev];
              data.logs.forEach(log => {
                newLogs.push({
                  type: log.type,
                  timestamp: log.timestamp,
                  message: log.message
                });
              });
              return newLogs;
            });
          }
        } catch (err) {
          console.error("Error parsing websocket message", err);
        }
      };
      
      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
      
      ws.onclose = () => {
        addLog("warning", "Mất kết nối WebSocket. Đang tự động kết nối lại...");
      };
    }
    
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [connectionStatus]);

  // Load report data when report tab is active
  useEffect(() => {
    if (currentTab === "report") {
      fetchReportData();
    }
  }, [currentTab]);

  const fetchReportData = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/report");
      if (res.ok) {
        const data = await res.json();
        const mapped = data.map((row, idx) => ({
          id: idx + 1,
          app_name: row.app_name || "AdVideo",
          video_name: row.video_name || "",
          saved_path: row.saved_path || "",
          platform: row.platform || "Facebook",
          area: row.area || "Vietnam",
          media_type: row.media_type || "Video",
          size: row.file_size ? `${(parseInt(row.file_size) / (1024 * 1024)).toFixed(1)} MB` : "0.0 MB",
          time: row.download_time || row.deployment_time || "",
          url: row.video_url || row.youtube_url || row.ad_url || ""
        }));
        setReportData(mapped);
      }
    } catch (err) {
      console.error("Lỗi tải dữ liệu báo cáo:", err);
    }
  };


  // Actions
  const handleConnect = async (e) => {
    if (e && typeof e.preventDefault === "function") {
      e.preventDefault();
    }
    setConnectionStatus("connecting");
    setConnectingText("Đang kiểm tra Chrome...");
    setErrorMessage("");
    addLog("info", `Đang kiểm tra kết nối tới Chrome debug port ${debugPort}...`);
    
    try {
      const res = await fetch(`http://127.0.0.1:8003/api/v1/socialpeta/status?port=${debugPort}`);
      const data = await res.json();
      
      if (data.chrome_connected) {
        if (data.logged_in) {
          setConnectionStatus("connected");
          addLog("success", "Đã kết nối với Chrome đang hoạt động và phiên đăng nhập còn hiệu lực!");
          handleRefreshTabs();
          setCurrentTab("tabs");
        } else {
          addLog("warning", "Tìm thấy Chrome gỡ lỗi nhưng chưa đăng nhập. Đang chuẩn bị cửa sổ đăng nhập...");
          setConnectingText("Đang mở cửa sổ đăng nhập...");
          const loginRes = await fetch(`http://127.0.0.1:8003/api/v1/socialpeta/login?port=${debugPort}`, {
            method: "POST"
          });
          const loginData = await loginRes.json();
          if (loginData.logged_in) {
            setConnectionStatus("connected");
            addLog("success", "Đăng nhập thành công!");
            handleRefreshTabs();
            setCurrentTab("tabs");
          } else {
            setConnectionStatus("error");
            setErrorMessage(loginData.message || "Đăng nhập thất bại.");
            addLog("error", "Đăng nhập thất bại hoặc cửa sổ đăng nhập bị đóng.");
          }
        }
      } else {
        addLog("warning", `Không tìm thấy tiến trình Chrome gỡ lỗi ở port ${debugPort}. Đang tiến hành tạo mới Chrome...`);
        setConnectingText("Đang khởi chạy Chrome debug...");
        
        const loginRes = await fetch(`http://127.0.0.1:8003/api/v1/socialpeta/login?port=${debugPort}`, {
          method: "POST"
        });
        const loginData = await loginRes.json();
        if (loginData.logged_in) {
          setConnectionStatus("connected");
          addLog("success", "Khởi tạo Chrome debug mới và đăng nhập thành công!");
          handleRefreshTabs();
          setCurrentTab("tabs");
        } else {
          setConnectionStatus("error");
          setErrorMessage(loginData.message || "Không thể khởi chạy Chrome hoặc đăng nhập thất bại.");
          addLog("error", "Khởi chạy Chrome thất bại hoặc trình duyệt bị đóng.");
        }
      }
    } catch (err) {
      setConnectionStatus("error");
      setErrorMessage(`Không thể kết nối tới Backend API tại http://127.0.0.1:8003. Lỗi: ${err.message}`);
      addLog("error", `Lỗi kết nối API: ${err.message}`);
    }
  };

  const handleDisconnect = () => {
    setConnectionStatus("disconnected");
    setIsDownloading(false);
    setActiveJobs([]);
    addLog("warning", "Đã ngắt kết nối khỏi trình duyệt Chrome.");
    setCurrentTab("setup");
  };

  const handleRefreshTabs = async () => {
    setIsRefreshingTabs(true);
    addLog("info", "Đang dò quét danh sách tab SocialPeta từ Chrome...");
    try {
      const res = await fetch(`http://127.0.0.1:8003/api/v1/socialpeta/tabs?port=${debugPort}`);
      if (!res.ok) {
        throw new Error(`Server status code ${res.status}`);
      }
      const data = await res.json();
      const mapped = data.map(t => ({
        tab_id: t.index,
        url: t.url,
        title: t.title || "SocialPeta Page",
        page: "—",
        type: (t.title || "").includes("TikTok") ? "TikTok Ads" : (t.title || "").includes("Facebook") ? "Facebook Ads" : "SocialPeta Page",
        status: "IDLE"
      }));
      setTabs(mapped);
      
      const newSelected = {};
      mapped.forEach(t => {
        newSelected[t.tab_id] = true;
      });
      setSelectedRows(newSelected);
      
      addLog("success", `Dò quét thành công. Phát hiện ${mapped.length} tab SocialPeta đang mở.`);
    } catch (err) {
      addLog("error", `Lỗi dò quét tab: ${err.message}`);
    } finally {
      setIsRefreshingTabs(false);
    }
  };

  const handleOpenDownloadModal = (type, targetId = null) => {
    setModalTargetType(type);
    if (type === "single" && targetId !== null) {
      setModalTargetType(`single-${targetId}`);
    }
    setIsDownloadModalOpen(true);
  };

  const handleStartDownload = async () => {
    setIsDownloadModalOpen(false);
    
    let tabsToStart = [];
    if (modalTargetType.startsWith("single-")) {
      const id = parseInt(modalTargetType.split("-")[1]);
      tabsToStart = tabs.filter(t => t.tab_id === id);
    } else if (modalTargetType === "all") {
      tabsToStart = tabs.filter(t => selectedRows[t.tab_id] || false);
      if (tabsToStart.length === 0) {
        tabsToStart = [...tabs];
      }
    }

    if (tabsToStart.length === 0) {
      addLog("error", "Không có tab nào được chọn để tải.");
      return;
    }

    addLog("info", `Đang gửi lệnh tải cho ${tabsToStart.length} tabs tới backend...`);
    
    try {
      const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tab_ids: tabsToStart.map(t => t.tab_id),
          pages: pagesToDownload,
          workers: workersCount
        })
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Yêu cầu thất bại");
      }
      
      const data = await res.json();
      addLog("success", data.message || "Đã kích hoạt quét và tải thành công!");
      setCurrentTab("dashboard");
      setIsDownloading(true);
    } catch (err) {
      addLog("error", `Lỗi kích hoạt tải: ${err.message}`);
      alert(`Không thể bắt đầu tải: ${err.message}`);
    }
  };

  const handleStopJob = async (tabId = null) => {
    addLog("info", tabId === null ? "Đang dừng toàn bộ các tab tải..." : `Đang dừng tab index #${tabId}...`);
    try {
      const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/stop", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          tab_id: tabId
        })
      });
      
      if (!res.ok) {
        throw new Error("Lỗi phản hồi từ backend");
      }
      
      const data = await res.json();
      addLog("warning", data.message || "Đã dừng tiến trình quét.");
    } catch (err) {
      addLog("error", `Lỗi khi dừng: ${err.message}`);
    }
  };

  const handleWorkersUpdate = (newVal) => {
    const val = Math.max(1, Math.min(16, newVal));
    setWorkersCount(val);
    if (isDownloading) {
      fetch("http://127.0.0.1:8003/api/v1/socialpeta/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tab_ids: activeJobs.filter(j => j.status === "RUNNING").map(j => j.tab_id),
          pages: pagesToDownload,
          workers: val
        })
      }).catch(err => console.error("Error updating workersCount dynamically", err));
    }
    addLog("info", `Đã cập nhật số luồng chạy đồng thời thành: ${val}`);
  };

  // Checkbox row states for tab manager
  const [selectedRows, setSelectedRows] = useState({});

  const handleToggleSelectAll = (e) => {
    const checked = e.target.checked;
    const newSelected = {};
    tabs.forEach(t => {
      newSelected[t.tab_id] = checked;
    });
    setSelectedRows(newSelected);
  };

  // Report Filters
  const handleFilterChange = (key, value) => {
    setReportFilters(prev => ({ ...prev, [key]: value }));
  };

  const getFilteredReportData = () => {
    return reportData.filter(row => {
      if (reportFilters.platform !== "all" && row.platform !== reportFilters.platform) return false;
      if (reportFilters.area !== "all" && row.area !== reportFilters.area) return false;
      if (reportFilters.appName !== "all") {
        const query = reportFilters.appName.toLowerCase();
        const matchesApp = row.app_name.toLowerCase().includes(query);
        const matchesFile = (row.video_name || "").toLowerCase().includes(query);
        if (!matchesApp && !matchesFile) return false;
      }
      if (reportFilters.mediaType !== "all" && row.media_type !== reportFilters.mediaType) return false;
      return true;
    });
  };


  const handleExportCSV = async () => {
    if (isElectron) {
      try {
        const filePath = await window.electronAPI.showSaveDialog("download_info.csv");
        if (filePath) {
          const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/export_csv_to_path?path=" + encodeURIComponent(filePath), {
            method: "POST"
          });
          if (res.ok) {
            addLog("success", `Đã lưu tệp báo cáo CSV thành công tại: ${filePath}`);
          } else {
            const err = await res.json();
            addLog("error", `Lỗi xuất CSV: ${err.detail || "Không rõ nguyên nhân"}`);
          }
        }
      } catch (err) {
        addLog("error", `Lỗi hộp thoại lưu file: ${err.message}`);
      }
    } else {
      window.open("http://127.0.0.1:8003/api/v1/socialpeta/export", "_blank");
      addLog("success", "Đã xuất dữ liệu download_info.csv thành công!");
    }
  };

  // Render Setup / Connection view as the Landing Page Layout
  if (currentTab === "setup") {
    return (
      <div className="landing-container">
        {/* Background glowing gradients */}
        <div className="landing-glow-1"></div>
        <div className="landing-glow-2"></div>

        {/* Navigation */}
        <nav className="landing-nav">
          <div className="logo-container" onClick={() => setCurrentTab('setup')}>
            <div className="logo-box">
              <Box size={28} strokeWidth={2.5} />
            </div>
            <span>SocialPeta Downloader</span>
          </div>
          <div className="landing-nav-links">
            <span className="landing-nav-link active">Home</span>
            <span className="landing-nav-link" onClick={() => connectionStatus === "connected" && setCurrentTab("tabs")}>Quản lý Tabs</span>
            <span className="landing-nav-link" onClick={() => connectionStatus === "connected" && setCurrentTab("dashboard")}>Đang tải xuống</span>
            <span className="landing-nav-link" onClick={() => setCurrentTab("report")}>Báo cáo & Export</span>
          </div>
          
          <div className="connection-indicator" style={{ border: "1px solid rgba(255,255,255,0.15)", background: "rgba(22,23,29,0.5)" }}>
            <span className={`indicator-dot ${connectionStatus === "connected" ? "connected" : connectionStatus === "connecting" ? "connecting" : "disconnected"}`}></span>
            <span style={{ fontWeight: "600", fontSize: "12px" }}>
              {connectionStatus === "connected" ? "CONNECTED" : connectionStatus === "connecting" ? "CONNECTING" : "OFFLINE"}
            </span>
          </div>
        </nav>

        {/* Hero content */}
        <main className="landing-hero">
          <div className="landing-hero-left">
            <h1 className="landing-hero-title">
              SocialPeta Ads Video & Image Downloader
            </h1>
            <p className="landing-hero-desc">
              Tự động điều khiển Chrome gỡ lỗi từ xa để tải xuống hàng loạt hình ảnh và video quảng cáo chất lượng cao trực tiếp từ các tab SocialPeta.
            </p>

            {/* Connection Form Card in Landing Hero */}
            <div className="setup-hero-card" style={{ marginTop: '24px' }}>
              <div onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleConnect(e);
                }
              }}>
                <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                  <label className="form-label">Chrome Debug Port</label>
                  <input
                    type="text"
                    className="form-input"
                    value={debugPort}
                    onChange={(e) => setDebugPort(e.target.value)}
                    placeholder="9222"
                    required
                    disabled={connectionStatus === "connecting" || connectionStatus === "connected"}
                    style={{ width: '100%', padding: '12px', background: 'var(--bg-input)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--text-primary)' }}
                  />
                </div>

                <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                  <label className="form-label">Số luồng tải tối đa (Workers)</label>
                  <input
                    type="number"
                    className="form-input"
                    min="1"
                    max="16"
                    value={workersCount}
                    onChange={(e) => setWorkersCount(parseInt(e.target.value))}
                    required
                    disabled={connectionStatus === "connecting" || connectionStatus === "connected"}
                    style={{ width: '100%', padding: '12px', background: 'var(--bg-input)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--text-primary)' }}
                  />
                </div>

                <div className="sys-suggestion" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
                  <Cpu size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Gợi ý: Hệ thống khuyên dùng <strong>{sysMonitorSuggestion} luồng</strong> dựa trên số CPU nhân thực tế của máy.
                  </span>
                </div>

                <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
                  <label className="form-label">Thư mục lưu tải xuống</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="text"
                      className="form-input"
                      value={downloadDir}
                      onChange={(e) => setDownloadDir(e.target.value)}
                      placeholder="Chọn thư mục tải xuống..."
                      required
                      disabled={isSavingConfig}
                      style={{ flex: 1, padding: '12px', background: 'var(--bg-input)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '14px' }}
                    />
                    {isElectron ? (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={async () => {
                            try {
                              const selected = await window.electronAPI.selectDirectory(downloadDir);
                              if (selected) {
                                setDownloadDir(selected);
                                setIsSavingConfig(true);
                                const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/config", {
                                  method: "POST",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ download_dir: selected })
                                });
                                if (res.ok) {
                                  const data = await res.json();
                                  setDownloadDir(data.download_dir);
                                  addLog("success", `Đã đổi thư mục tải xuống thành: ${data.download_dir}`);
                                } else {
                                  const err = await res.json();
                                  addLog("error", `Lỗi đổi thư mục: ${err.detail || "Không rõ nguyên nhân"}`);
                                }
                              }
                            } catch (err) {
                              addLog("error", `Lỗi chọn thư mục: ${err.message}`);
                            } finally {
                              setIsSavingConfig(false);
                            }
                          }}
                          disabled={isSavingConfig}
                          style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        >
                          <FolderOpen size={16} />
                          <span>Chọn</span>
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={async () => {
                            try {
                              setIsSavingConfig(true);
                              const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/config", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ download_dir: downloadDir })
                              });
                              if (res.ok) {
                                const data = await res.json();
                                setDownloadDir(data.download_dir);
                                addLog("success", `Đã lưu thư mục tải xuống thành công: ${data.download_dir}`);
                              } else {
                                const err = await res.json();
                                addLog("error", `Lỗi lưu thư mục: ${err.detail || "Không rõ nguyên nhân"}`);
                              }
                            } catch (err) {
                              addLog("error", `Lỗi lưu thư mục: ${err.message}`);
                            } finally {
                              setIsSavingConfig(false);
                            }
                          }}
                          disabled={isSavingConfig}
                          style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        >
                          <span>Lưu</span>
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          try {
                            setIsSavingConfig(true);
                            const res = await fetch("http://127.0.0.1:8003/api/v1/socialpeta/config", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ download_dir: downloadDir })
                            });
                            if (res.ok) {
                              const data = await res.json();
                              setDownloadDir(data.download_dir);
                              addLog("success", `Đã lưu thư mục tải xuống thành công: ${data.download_dir}`);
                            } else {
                              const err = await res.json();
                              addLog("error", `Lỗi lưu thư mục: ${err.detail || "Không rõ nguyên nhân"}`);
                            }
                          } catch (err) {
                            addLog("error", `Lỗi lưu thư mục: ${err.message}`);
                          } finally {
                            setIsSavingConfig(false);
                          }
                        }}
                        disabled={isSavingConfig}
                        style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <span>Lưu</span>
                      </button>
                    )}
                  </div>
                </div>

                {connectionStatus !== "connected" ? (
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ width: "100%", justifyContent: "center", padding: "14px 28px", fontSize: "15px" }}
                    disabled={connectionStatus === "connecting"}
                    onClick={handleConnect}
                  >
                    {connectionStatus === "connecting" ? (
                      <>
                        <RotateCw size={16} className="animate-spin" style={{ animation: "spin 1s linear infinite", marginRight: '8px' }} />
                        <span>{connectingText}</span>
                      </>
                    ) : (
                      <>
                        <Globe size={18} style={{ marginRight: '8px' }} />
                        <span>Bắt đầu kết nối</span>
                      </>
                    )}
                  </button>
                ) : (
                  <div style={{ display: "flex", gap: "12px" }}>
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ flex: 1, justifyContent: "center" }}
                      onClick={() => setCurrentTab("tabs")}
                    >
                      Quản lý Tabs
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ flex: 1, justifyContent: "center" }}
                      onClick={handleDisconnect}
                    >
                      Ngắt kết nối
                    </button>
                  </div>
                )}
              </div>

              {/* Alerts inside setup-hero-card */}
              {connectionStatus === "error" && (
                <div className="status-alert error" style={{ display: 'flex', gap: '12px', marginTop: '20px', padding: '16px', borderRadius: '8px' }}>
                  <AlertCircle size={20} style={{ flexShrink: 0 }} />
                  <div>
                    <strong style={{ fontWeight: '600' }}>Lỗi kết nối Chrome Debug:</strong>
                    <p style={{ marginTop: "4px", fontSize: '13px' }}>{errorMessage}</p>
                    <p style={{ marginTop: "8px", fontWeight: "600", fontSize: '13px' }}>Cách khắc phục:</p>
                    <ul className="instructions-list" style={{ marginTop: '4px', paddingLeft: '18px', fontSize: '13px' }}>
                      <li>Tắt hoàn toàn trình duyệt Chrome đang mở.</li>
                      <li>
                        Chạy Chrome qua Terminal hoặc Run (Win + R) bằng câu lệnh sau:
                        <code style={{ display: "block", backgroundColor: "rgba(0,0,0,0.3)", padding: "8px", margin: "6px 0", borderRadius: "4px", fontSize: "11px", wordBreak: "break-all", border: "1px solid rgba(255,255,255,0.05)" }}>
                          chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_profile"
                        </code>
                      </li>
                      <li>Sau khi Chrome mở lên, truy cập trang SocialPeta và thử nhấn kết nối lại ở đây.</li>
                    </ul>
                  </div>
                </div>
              )}

              {connectionStatus === "connected" && (
                <div className="status-alert success" style={{ display: 'flex', gap: '12px', marginTop: '20px', padding: '16px', borderRadius: '8px' }}>
                  <CheckCircle size={20} style={{ flexShrink: 0 }} />
                  <div>
                    <strong style={{ fontWeight: '600' }}>Kết nối thành công!</strong>
                    <p style={{ marginTop: "4px", fontSize: '13px' }}>Đã liên kết thành công với Chrome đang chạy. Bạn có thể bắt đầu chọn các tab SocialPeta đang hoạt động để tải xuống.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Stats Row */}
            <div className="landing-stats-row" style={{ marginTop: '32px' }}>
              <div className="landing-stat-item">
                <div className="landing-stat-icon-wrapper">
                  <Globe size={22} />
                </div>
                <div>
                  <div className="landing-stat-num">9222</div>
                  <div className="landing-stat-label">port mặc định</div>
                </div>
              </div>

              <div className="landing-stat-item" style={{ borderLeft: '1px solid rgba(255,255,255,0.08)', paddingLeft: '28px' }}>
                <div className="landing-stat-icon-wrapper">
                  <Cpu size={22} />
                </div>
                <div>
                  <div className="landing-stat-num">{workersCount} Thớt</div>
                  <div className="landing-stat-label">luồng tải đồng thời</div>
                </div>
              </div>

              <div className="landing-stat-item" style={{ borderLeft: '1px solid rgba(255,255,255,0.08)', paddingLeft: '28px' }}>
                <div className="landing-stat-icon-wrapper">
                  <Layers size={22} />
                </div>
                <div>
                  <div className="landing-stat-num">{tabs.length} Tabs</div>
                  <div className="landing-stat-label">SocialPeta đang chạy</div>
                </div>
              </div>
            </div>
          </div>

          <div className="landing-hero-right">
            <svg
              className="landing-folder-art"
              viewBox="0 0 500 400"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Back folder plate: x=32 to x=448 (width 416) */}
              <path
                d="M32 100C32 86.7452 42.7452 76 56 76H150C158.528 76 166.425 80.5362 170.76 87.9255L181.24 105.749C183.407 109.444 187.356 111.71 191.62 111.71H424C437.255 111.71 448 122.465 448 135.71V332C448 345.255 437.255 356 424 356H56C42.7452 356 32 345.255 32 332V100Z"
                fill="#1836d9"
              />
              {/* Inner papers, resized and centered to folder width 416 (center x=240) */}
              <rect
                x="120"
                y="110"
                width="320"
                height="200"
                rx="12"
                fill="#e2e6f3"
                transform="rotate(6 280 210)"
              />
              <rect
                x="100"
                y="114"
                width="320"
                height="200"
                rx="12"
                fill="#f1f3fa"
                transform="rotate(3 260 214)"
              />
              <rect
                x="80"
                y="118"
                width="320"
                height="200"
                rx="12"
                fill="#ffffff"
              />
              {/* Front flap: x=32 to x=448 (width 416) to align perfectly with the back plate */}
              <path
                d="M32 160C32 146.745 42.7452 136 56 136H424C437.255 136 448 146.745 448 160V348C448 361.255 437.255 372 424 372H56C42.7452 372 32 361.255 32 348V160Z"
                fill="#3051ff"
                style={{ filter: 'drop-shadow(0 -10px 25px rgba(0,0,0,0.15))' }}
              />
            </svg>
          </div>
        </main>
      </div>
    );
  }

  // Otherwise render app with sidebar
  return (
    <div className="app-container">
      {/* Persistent Left Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div 
            className="logo-container" 
            onClick={() => {
              setCurrentTab('setup');
            }}
          >
            <div className="logo-box">
              <Box size={28} strokeWidth={2.5} />
            </div>
            <span>SocialPeta DL</span>
          </div>
        </div>

        <div className="sidebar-content">
          <div className="sidebar-nav">
            {/* Control Panel Section */}
            <div className="sidebar-nav-group">
              <h4 className="sidebar-group-title">Menu Điều khiển</h4>
              <ul className="sidebar-menu-list">
                
                {/* Connections / Setup */}
                <li className="sidebar-menu-item">
                  <div
                    className={`sidebar-link ${currentTab === "setup" ? "active" : ""}`}
                    onClick={() => setCurrentTab("setup")}
                  >
                    <div className="sidebar-link-left">
                      <Globe size={18} />
                      <span>Kết nối Chrome</span>
                    </div>
                    <span className={`sidebar-badge ${connectionStatus === "connected" ? "success" : "error"}`}>
                      {connectionStatus === "connected" ? "CONNECTED" : "OFFLINE"}
                    </span>
                  </div>
                </li>

                {/* Tab Manager */}
                <li className="sidebar-menu-item">
                  <div
                    className={`sidebar-link ${
                      connectionStatus !== "connected"
                        ? "disabled"
                        : currentTab === "tabs"
                        ? "active"
                        : ""
                    }`}
                    style={connectionStatus !== "connected" ? { opacity: 0.4, cursor: "not-allowed" } : {}}
                    onClick={() => connectionStatus === "connected" && setCurrentTab("tabs")}
                  >
                    <div className="sidebar-link-left">
                      <Layers size={18} />
                      <span>Quản lý Tabs</span>
                    </div>
                    <ChevronRight size={14} className="sidebar-link-chevron" />
                  </div>

                  {/* Submenu actions under Quản lý Tabs */}
                  {currentTab === 'tabs' && (
                    <ul className="sidebar-sub-list">
                      <li className="sidebar-sub-item">
                        <div 
                          className="sidebar-sub-link active"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRefreshTabs();
                          }}
                        >
                          Làm mới danh sách
                        </div>
                      </li>
                      <li className="sidebar-sub-item">
                        <div 
                          className="sidebar-sub-link"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (Object.values(selectedRows).filter(Boolean).length > 0) {
                              handleOpenDownloadModal("all");
                            }
                          }}
                          style={Object.values(selectedRows).filter(Boolean).length === 0 ? { opacity: 0.5, cursor: "not-allowed" } : {}}
                        >
                          Tải đã chọn ({Object.values(selectedRows).filter(Boolean).length})
                        </div>
                      </li>
                    </ul>
                  )}
                </li>

                {/* Dashboard / Active Jobs */}
                <li className="sidebar-menu-item">
                  <div
                    className={`sidebar-link ${
                      connectionStatus !== "connected"
                        ? "disabled"
                        : currentTab === "dashboard"
                        ? "active"
                        : ""
                    }`}
                    style={connectionStatus !== "connected" ? { opacity: 0.4, cursor: "not-allowed" } : {}}
                    onClick={() => connectionStatus === "connected" && setCurrentTab("dashboard")}
                  >
                    <div className="sidebar-link-left">
                      <Activity size={18} />
                      <span>Đang tải xuống</span>
                    </div>
                    {isDownloading && (
                      <span className="sidebar-badge error" style={{ animation: "statusPulse 1.5s infinite" }}>
                        LIVE
                      </span>
                    )}
                  </div>
                </li>

                {/* Report Screen */}
                <li className="sidebar-menu-item">
                  <div
                    className={`sidebar-link ${currentTab === "report" ? "active" : ""}`}
                    onClick={() => setCurrentTab("report")}
                  >
                    <div className="sidebar-link-left">
                      <FileSpreadsheet size={18} />
                      <span>Báo cáo & Export</span>
                    </div>
                    <ChevronRight size={14} className="sidebar-link-chevron" />
                  </div>
                </li>
              </ul>
            </div>
          </div>

          {/* Sidebar Footer workers details */}
          <div className="sidebar-footer">
            <div className="sidebar-storage-info">
              <div className="sidebar-storage-label">
                <Cpu size={15} />
                <span>Số luồng chạy</span>
              </div>
              <span className="sidebar-storage-percent">{workersCount} Workers</span>
            </div>
            <div className="sidebar-progress-container">
              <div
                className="sidebar-progress-bar"
                style={{ width: `${(workersCount / 16) * 100}%` }}
              ></div>
            </div>
            {downloadDir && (
              <div 
                className="sidebar-storage-info" 
                onClick={async () => {
                  try {
                    await fetch("http://127.0.0.1:8003/api/v1/socialpeta/open_folder", { method: "POST" });
                  } catch (e) {
                    console.error("Lỗi mở thư mục:", e);
                  }
                }}
                title={downloadDir}
                style={{ marginTop: '14px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start', background: 'rgba(255,255,255,0.02)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.04)' }}
              >
                <div className="sidebar-storage-label" style={{ width: '100%', justifyContent: 'space-between', display: 'flex' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FolderOpen size={13} style={{ color: 'var(--color-primary)' }} />
                    <span style={{ fontSize: '11px', fontWeight: '600' }}>Thư mục lưu</span>
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--color-primary)', textDecoration: 'underline' }}>Mở</span>
                </div>
                <div style={{ 
                  fontSize: '11px', 
                  color: 'var(--text-secondary)', 
                  whiteSpace: 'nowrap', 
                  overflow: 'hidden', 
                  textOverflow: 'ellipsis', 
                  width: '100%',
                  textAlign: 'left',
                  marginTop: '2px'
                }}>
                  {downloadDir}
                </div>
              </div>
            )}
            {connectionStatus === "connected" && (
              <button 
                className="btn-upgrade" 
                style={{ width: '100%', marginTop: '16px', background: 'rgba(255, 77, 90, 0.1)', color: 'var(--color-image)', borderColor: 'rgba(255, 77, 90, 0.2)' }}
                onClick={handleDisconnect}
              >
                <LogOut size={14} style={{ marginRight: "6px" }} />
                <span>Ngắt kết nối Chrome</span>
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main content pane */}
      <div className="main-content">
        {/* Top Header bar */}
        <header className="topbar">
          <div className="topbar-title" style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'var(--font-display)' }}>
            {currentTab === "tabs" && "Danh sách Tab SocialPeta"}
            {currentTab === "dashboard" && "Tiến trình tải xuống thời gian thực"}
            {currentTab === "report" && "Dữ liệu tải xuống & Xuất báo cáo"}
          </div>

          {/* Quick Actions (Connection status & Config Settings icon) */}
          <div className="topbar-right">
            <div className="connection-indicator">
              <span
                className={`indicator-dot ${
                  connectionStatus === "connected"
                    ? "connected"
                    : connectionStatus === "connecting"
                    ? "connecting"
                    : "disconnected"
                }`}
              ></span>
              <span style={{ textTransform: "capitalize", fontWeight: "600" }}>
                {connectionStatus === "connected"
                  ? `Chrome connected (Port: ${debugPort})`
                  : connectionStatus === "connecting"
                  ? "Connecting..."
                  : "Offline"}
              </span>
            </div>

            <div className="avatar-wrapper" onClick={() => setCurrentTab('setup')} title="Cấu hình kết nối">
              <div className="avatar-img" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--color-primary-light)', color: 'var(--color-primary)', width: '100%', height: '100%', borderRadius: '50%' }}>
                <Settings size={18} />
              </div>
            </div>
          </div>
        </header>

        {/* SCREEN 2: TAB MANAGER */}
        {currentTab === "tabs" && (
          <div className="dashboard-content">
            <div className="dashboard-header-row">
              <div className="overview-pill">
                <Layers size={16} className="overview-pill-icon" />
                <span>– Tabs Manager</span>
              </div>

              <div className="header-actions">
                <button className="btn-secondary" onClick={handleRefreshTabs} disabled={isRefreshingTabs}>
                  <RefreshCw size={16} className={isRefreshingTabs ? "animate-spin" : ""} style={isRefreshingTabs ? { animation: "spin 1s linear infinite" } : {}} />
                  <span>Làm mới tab</span>
                </button>
                <button
                  className="btn-primary"
                  disabled={Object.values(selectedRows).filter(Boolean).length === 0}
                  onClick={() => handleOpenDownloadModal("all")}
                >
                  <Download size={16} />
                  <span>Tải đã chọn ({Object.values(selectedRows).filter(Boolean).length})</span>
                </button>
              </div>
            </div>

            <section className="section" style={{ marginBottom: 0 }}>
              <h3 className="section-title">Danh sách tab SocialPeta đang hoạt động</h3>
              <div className="recent-table-container">
                <table className="recent-table">
                  <thead>
                    <tr>
                      <th style={{ width: "40px" }}>
                        <label className="custom-checkbox">
                          <input
                            type="checkbox"
                            onChange={handleToggleSelectAll}
                            checked={tabs.length > 0 && tabs.every(t => selectedRows[t.tab_id])}
                          />
                          <span className="checkmark"></span>
                        </label>
                      </th>
                      <th>Số Tab</th>
                      <th>Loại Trang</th>
                      <th>Đường Dẫn URL</th>
                      <th>Trang Hiện Tại</th>
                      <th>Trạng Thái</th>
                      <th style={{ width: "160px", textAlign: "right" }}>Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tabs.map((tab) => (
                      <tr key={tab.tab_id} className={selectedRows[tab.tab_id] ? "selected" : ""}>
                        <td>
                          <label className="custom-checkbox">
                            <input
                              type="checkbox"
                              checked={!!selectedRows[tab.tab_id]}
                              onChange={() => {
                                setSelectedRows(prev => ({
                                  ...prev,
                                  [tab.tab_id]: !prev[tab.tab_id]
                                }));
                              }}
                            />
                            <span className="checkmark"></span>
                          </label>
                        </td>
                        <td style={{ fontWeight: "600", color: "var(--text-secondary)" }}>#{tab.tab_id}</td>
                        <td style={{ fontWeight: "600" }}>{tab.type}</td>
                        <td style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
                          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                            <span style={{ fontWeight: "600", color: "var(--text-primary)", fontSize: "14px", maxWidth: "340px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {tab.title || tab.type || "SocialPeta Page"}
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span style={{ maxWidth: "340px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tab.url}</span>
                              <a href={tab.url} target="_blank" rel="noreferrer" style={{ color: "var(--color-primary)" }}>
                                <ExternalLink size={12} />
                              </a>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="sidebar-badge" style={{ backgroundColor: "rgba(255, 255, 255, 0.04)" }}>{tab.page || "—"}</span>
                        </td>
                        <td>
                          <span
                            className={`sidebar-badge ${
                              tab.status === "NEW" ? "success" : tab.status === "ĐANG TẢI" ? "error" : ""
                            }`}
                            style={tab.status === "IDLE" ? { backgroundColor: "rgba(255,255,255,0.06)", color: "var(--text-secondary)" } : {}}
                          >
                            {tab.status}
                          </span>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button
                            className="btn-secondary"
                            style={{ padding: "6px 12px", fontSize: "13px" }}
                            onClick={() => handleOpenDownloadModal("single", tab.tab_id)}
                          >
                            Tải tab này
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {/* SCREEN 3: REALTIME DASHBOARD */}
        {currentTab === "dashboard" && (
          <div className="dashboard-content">
            <div className="dashboard-header-row">
              <div className="overview-pill">
                <Activity size={16} className="overview-pill-icon" />
                <span>– Realtime Dashboard</span>
              </div>

              <div className="header-actions">
                <button 
                  className="btn-secondary" 
                  onClick={() => handleStopJob(null)} 
                  disabled={activeJobs.length === 0}
                  style={{ color: "var(--color-image)", borderColor: "rgba(255, 77, 90, 0.2)" }}
                >
                  <Square size={14} fill="currentColor" />
                  <span>Dừng Tất Cả</span>
                </button>
              </div>
            </div>

            {/* Storage Cards Overview */}
            <section className="section">
              <h3 className="section-title">Thống kê tiến trình tải</h3>
              <div className="storage-grid">
                
                {/* Total Pending */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box video">
                      <Activity size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Chờ Tải</h4>
                    <p className="storage-card-count">{stats.pending} / {stats.total} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Tiến độ tổng quan</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar video" style={{ width: `${stats.total > 0 ? (stats.done / stats.total) * 100 : 0}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Successful Done */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box music">
                      <CheckCircle size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Thành Công</h4>
                    <p className="storage-card-count">{stats.done} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Tải về thư mục local</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar music" style={{ width: `${stats.total > 0 ? (stats.done / stats.total) * 100 : 0}%` }}></div>
                      </div>
                      {downloadDir && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '12px', cursor: 'pointer' }}
                             onClick={async () => {
                               try {
                                 await fetch("http://127.0.0.1:8003/api/v1/socialpeta/open_folder", { method: "POST" });
                               } catch (e) {
                                 console.error("Lỗi mở thư mục:", e);
                               }
                             }}
                             title={`Mở thư mục: ${downloadDir}`}>
                          <FolderOpen size={12} style={{ color: 'var(--color-music)', flexShrink: 0 }} />
                          <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textDecoration: 'underline', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                            {downloadDir}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Duplicates */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box doc">
                      <SlidersHorizontal size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Trùng Lặp</h4>
                    <p className="storage-card-count">{stats.duplicate} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Bỏ qua không lưu trùng</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar doc" style={{ width: `${stats.total > 0 ? (stats.duplicate / stats.total) * 100 : 0}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Failed */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box image">
                      <AlertCircle size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Thất Bại</h4>
                    <p className="storage-card-count">{stats.failed} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Lỗi CDN / Request timeout</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar image" style={{ width: `${stats.total > 0 ? (stats.failed / stats.total) * 100 : 0}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Workers Count Controller inside a card */}
            <div className="storage-card" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px', flexDirection: 'row' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div className="storage-icon-box doc" style={{ width: '48px', height: '48px', borderRadius: '10px' }}>
                  <Cpu size={22} />
                </div>
                <div>
                  <h4 style={{ fontWeight: '600', fontSize: '15px' }}>Điều Chỉnh Luồng Xử Lý</h4>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>Thay đổi số lượng Chrome tab tải song song mà không cần khởi động lại.</p>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button className="btn-secondary" style={{ padding: '8px 16px', borderRadius: '8px' }} onClick={() => handleWorkersUpdate(workersCount - 1)}>-</button>
                <span style={{ fontSize: '18px', fontWeight: '700', width: '30px', textAlign: 'center', fontFamily: 'var(--font-display)' }}>{workersCount}</span>
                <button className="btn-secondary" style={{ padding: '8px 16px', borderRadius: '8px' }} onClick={() => handleWorkersUpdate(workersCount + 1)}>+</button>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px' }}>(Tối đa 16 luồng)</span>
              </div>
            </div>

            {/* Two Column Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px', marginTop: '24px' }}>
              
              {/* Active Jobs table */}
              <div className="recent-table-container">
                <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--color-border)" }}>
                  <h4 style={{ fontWeight: "600", fontSize: "15px" }}>Các Tab Đang Hoạt Động</h4>
                </div>
                
                {activeJobs.length === 0 ? (
                  <div style={{ padding: "40px", textAlign: "center", color: "var(--text-secondary)" }}>
                    Không có tiến trình tải nào đang hoạt động.
                  </div>
                ) : (
                  <div style={{ overflowY: "auto", maxHeight: "300px" }}>
                    <table className="recent-table">
                      <thead>
                        <tr>
                          <th>Tab ID</th>
                          <th>Mục Tiêu</th>
                          <th>Thành Công</th>
                          <th>Tiến độ</th>
                          <th style={{ textAlign: "right" }}>Thao tác</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeJobs.map((job) => (
                          <tr key={job.tab_id}>
                            <td style={{ fontWeight: "600" }}>#{job.tab_id}</td>
                            <td>
                              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                                <span style={{ fontWeight: "600", fontSize: "13px" }}>{job.type}</span>
                                <span style={{ fontSize: "11px", color: "var(--text-muted)", maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {job.url}
                                </span>
                              </div>
                            </td>
                            <td style={{ fontSize: "13px" }}>
                              <span style={{ color: "var(--color-music)" }}>{job.done}</span>
                              <span style={{ color: "var(--text-muted)" }}>/{job.pending + job.done + job.failed}</span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '100px' }}>
                                <div className="storage-mini-progress" style={{ flex: 1, height: '6px' }}>
                                  <div
                                    className={`storage-mini-bar ${job.status === "DONE" ? "music" : "video"}`}
                                    style={{ width: `${job.progress}%` }}
                                  ></div>
                                </div>
                                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{job.progress}%</span>
                              </div>
                            </td>
                            <td style={{ textAlign: "right" }}>
                              {job.status === "RUNNING" ? (
                                <button
                                  className="topbar-icon-btn"
                                  style={{ color: "var(--color-image)" }}
                                  onClick={() => handleStopJob(job.tab_id)}
                                >
                                  <Square size={14} fill="currentColor" />
                                </button>
                              ) : job.status === "DONE" ? (
                                <span className="sidebar-badge success">DONE</span>
                              ) : (
                                <span className="sidebar-badge error">STOPPED</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Console Logs */}
              <div className="log-panel">
                <div className="log-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="indicator-dot connected" style={{ width: "6px", height: "6px" }}></span>
                    <h4 style={{ fontWeight: "600", fontSize: "15px" }}>Realtime Console Logs</h4>
                  </div>
                  <button className="btn-secondary" style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => setLogs([])}>
                    Clear Logs
                  </button>
                </div>
                
                <div className="log-body">
                  {logs.length === 0 ? (
                    <div className="log-row info">
                      [SYSTEM] Đang chờ kết nối WebSocket từ localhost:8000/ws/status...
                    </div>
                  ) : (
                    logs.map((log, idx) => (
                      <div key={idx} className={`log-row ${log.type}`}>
                        <span className="log-row timestamp">[{log.timestamp}]</span>
                        <span>{log.message}</span>
                      </div>
                    ))
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>

            </div>
          </div>
        )}

        {/* SCREEN 4: REPORT SCREEN */}
        {currentTab === "report" && (
          <div className="dashboard-content">
            <div className="dashboard-header-row">
              <div className="overview-pill">
                <FileSpreadsheet size={16} className="overview-pill-icon" />
                <span>– Reports & Export</span>
              </div>
            </div>

            {/* Storage Cards Overview */}
            <section className="section">
              <h3 className="section-title">Tổng quan phiên tải</h3>
              <div className="storage-grid">
                
                {/* Videos */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box video">
                      <Download size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Video Ads</h4>
                    <p className="storage-card-count">{reportData.reduce((acc, row) => acc + (row.media_type === "Video" ? 1 : 0), 0)} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Định dạng MP4</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar video" style={{ width: '65%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Images */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box music">
                      <FileSpreadsheet size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Hình Ảnh</h4>
                    <p className="storage-card-count">{reportData.reduce((acc, row) => acc + (row.media_type === "Image" ? 1 : 0), 0)} tệp</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Định dạng JPG/PNG</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar music" style={{ width: '35%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Storage size */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box doc">
                      <Cpu size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Tổng Dung Lượng</h4>
                    <p className="storage-card-count">{totalSizeMB} MB</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>Tốc độ tải trung bình ~4MB/s</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar doc" style={{ width: `${Math.min(100, (parseFloat(totalSizeMB) / 200) * 100)}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Channels */}
                <div className="storage-card">
                  <div className="storage-card-header">
                    <div className="storage-icon-box image">
                      <Layers size={22} />
                    </div>
                  </div>
                  <div className="storage-card-footer">
                    <h4 className="storage-card-title">Kênh Quảng Cáo</h4>
                    <p className="storage-card-count">{uniquePlatforms} Kênh chính</p>
                    <div style={{ marginTop: '16px' }}>
                      <div className="storage-progress-meta">
                        <span>{platformNames}</span>
                      </div>
                      <div className="storage-mini-progress">
                        <div className="storage-mini-bar image" style={{ width: uniquePlatforms > 0 ? '100%' : '0%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Filters */}
            <div className="filter-bar">
              <div className="filter-item">
                <label className="form-label" style={{ fontSize: "11px" }}>Kênh (Platform)</label>
                <select
                  className="filter-select"
                  value={reportFilters.platform}
                  onChange={(e) => handleFilterChange("platform", e.target.value)}
                >
                  <option value="all">Tất cả Kênh</option>
                  <option value="Facebook">Facebook</option>
                  <option value="TikTok">TikTok</option>
                  <option value="Google">Google Ads</option>
                </select>
              </div>

              <div className="filter-item">
                <label className="form-label" style={{ fontSize: "11px" }}>Khu vực (Area)</label>
                <select
                  className="filter-select"
                  value={reportFilters.area}
                  onChange={(e) => handleFilterChange("area", e.target.value)}
                >
                  <option value="all">Tất cả Khu vực</option>
                  <option value="Vietnam">Vietnam</option>
                  <option value="Thailand">Thailand</option>
                  <option value="Singapore">Singapore</option>
                  <option value="USA">USA</option>
                </select>
              </div>

              <div className="filter-item">
                <label className="form-label" style={{ fontSize: "11px" }}>Định dạng (Media Type)</label>
                <select
                  className="filter-select"
                  value={reportFilters.mediaType}
                  onChange={(e) => handleFilterChange("mediaType", e.target.value)}
                >
                  <option value="all">Tất cả định dạng</option>
                  <option value="Video">Video</option>
                  <option value="Image">Hình ảnh</option>
                </select>
              </div>

              <div className="filter-item" style={{ minWidth: "200px" }}>
                <label className="form-label" style={{ fontSize: "11px" }}>Tên ứng dụng (App Name)</label>
                <input
                  type="text"
                  className="form-input"
                  style={{ padding: "10px 14px", fontSize: "13px", background: 'var(--bg-input)', border: '1px solid var(--color-border)', borderRadius: '8px' }}
                  placeholder="Tìm theo tên ứng dụng..."
                  value={reportFilters.appName === "all" ? "" : reportFilters.appName}
                  onChange={(e) => handleFilterChange("appName", e.target.value || "all")}
                />
              </div>

              <div style={{ display: "flex", gap: "10px", height: '40px' }}>
                <button className="btn-secondary" style={{ padding: "10px 20px" }} onClick={() => setReportFilters({ platform: "all", area: "all", appName: "all", mediaType: "all" })}>
                  Reset
                </button>
                <button className="btn-primary" onClick={handleExportCSV}>
                  <Download size={16} />
                  <span>Xuất CSV</span>
                </button>
              </div>
            </div>

            {/* Report Table */}
            <div className="recent-table-container">
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--color-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h4 style={{ fontWeight: "600", fontSize: "15px" }}>Thông Tin Tải Chi Tiết (download_info.csv)</h4>
                <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  Hiển thị <strong>{getFilteredReportData().length}</strong> dòng
                </span>
              </div>
              <table className="recent-table">
                <thead>
                  <tr>
                    <th>Tên tệp / Ứng dụng</th>
                    <th>Kênh</th>
                    <th>Khu vực</th>
                    <th>Định dạng</th>
                    <th>Dung lượng</th>
                    <th>Thời gian tải</th>
                    <th style={{ textAlign: "right" }}>Xem gốc</th>
                  </tr>
                </thead>
                <tbody>
                  {getFilteredReportData().map((row) => (
                    <tr key={row.id}>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span style={{ fontWeight: "600", fontSize: "13px", color: "var(--text-primary)", wordBreak: "break-all" }}>
                            {row.video_name || "—"}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--text-secondary)", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px" }}>
                            <span style={{ color: "var(--text-muted)" }}>App:</span>
                            <span>{row.app_name}</span>
                            {row.saved_path && (
                              <>
                                <span style={{ color: "var(--color-border)" }}>•</span>
                                <span style={{ fontFamily: "monospace", color: "var(--text-muted)" }}>{row.saved_path}</span>
                              </>
                            )}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`sidebar-badge ${row.platform === "Facebook" ? "success" : row.platform === "TikTok" ? "error" : "idle"}`}>
                          {row.platform}
                        </span>
                      </td>
                      <td>{row.area}</td>
                      <td style={{ color: "var(--text-secondary)" }}>{row.media_type}</td>
                      <td style={{ color: "var(--text-secondary)" }}>{row.size}</td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "13px" }}>{row.time}</td>
                      <td style={{ textAlign: "right" }}>
                        <a href={row.url} target="_blank" rel="noreferrer" className="topbar-icon-btn" style={{ display: "inline-flex" }}>
                          <ExternalLink size={14} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

            </div>
          </div>
        )}
      </div>

      {/* DOWNLOAD PAGE-COUNT POPUP MODAL */}
      {isDownloadModalOpen && (
        <div className="modal-overlay" onClick={() => setIsDownloadModalOpen(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <button className="modal-close-btn" onClick={() => setIsDownloadModalOpen(false)}>
              <X size={18} />
            </button>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h3 className="modal-filename" style={{ fontSize: '18px' }}>Cấu hình số trang cần tải</h3>
              
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                Nhập số lượng trang quảng cáo (pages) muốn thu thập từ SocialPeta. 
                Mỗi trang chứa khoảng 10-12 video hoặc ảnh quảng cáo tương ứng.
              </p>

              <div className="form-group">
                <label className="form-label">Số trang muốn tải</label>
                <input
                  type="number"
                  className="form-input"
                  min="1"
                  max="100"
                  value={pagesToDownload}
                  onChange={(e) => setPagesToDownload(parseInt(e.target.value))}
                  required
                  style={{ width: '100%', marginTop: '8px', padding: '10px 14px', background: 'var(--bg-input)', border: '1px solid var(--color-border)', borderRadius: '8px', color: 'var(--text-primary)' }}
                />
              </div>

              <div className="modal-actions" style={{ justifyContent: 'flex-end', marginTop: '8px' }}>
                <button className="btn-secondary" onClick={() => setIsDownloadModalOpen(false)}>
                  Hủy bỏ
                </button>
                <button className="btn-primary" onClick={handleStartDownload}>
                  Bắt đầu tải
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

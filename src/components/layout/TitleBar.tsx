import React, { useEffect, useState } from 'react';
import { Minus, Square, Copy, X, Sparkles, FolderKanban } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';

export const TitleBar: React.FC = () => {
  const { activeProject } = useProject();
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    const checkMaximized = async () => {
      if (window.electronAPI?.isWindowMaximized) {
        const max = await window.electronAPI.isWindowMaximized();
        setIsMaximized(max);
      }
    };
    checkMaximized();
  }, []);

  const handleMinimize = () => {
    window.electronAPI?.minimizeWindow?.();
  };

  const handleMaximize = async () => {
    if (window.electronAPI?.maximizeWindow) {
      await window.electronAPI.maximizeWindow();
      const max = await window.electronAPI.isWindowMaximized();
      setIsMaximized(max);
    }
  };

  const handleClose = () => {
    window.electronAPI?.closeWindow?.();
  };

  return (
    <header className="titlebar">
      <div className="titlebar-left">
        <div className="titlebar-logo">
          <div className="titlebar-logo-icon">
            <Sparkles size={13} color="#050811" />
          </div>
          <span>MediaForge AI</span>
        </div>
        <span className="titlebar-badge">v1.0 Pro</span>
      </div>

      <div className="titlebar-center">
        {activeProject ? (
          <div className="titlebar-project-pill" title={`Project Path: ${activeProject.projectDirectory}`}>
            <FolderKanban size={13} color="var(--cyan)" />
            <span>{activeProject.name}</span>
            <span style={{ color: 'var(--text-muted)' }}>•</span>
            <span style={{ color: 'var(--text-cyan)', textTransform: 'uppercase' }}>
              {activeProject.sourceLanguage} → {activeProject.targetLanguage}
            </span>
          </div>
        ) : (
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No Active Project</span>
        )}
      </div>

      <div className="titlebar-right">
        <button className="titlebar-btn" onClick={handleMinimize} title="Minimize">
          <Minus size={13} />
        </button>
        <button className="titlebar-btn" onClick={handleMaximize} title={isMaximized ? 'Restore' : 'Maximize'}>
          {isMaximized ? <Copy size={12} /> : <Square size={12} />}
        </button>
        <button className="titlebar-btn close" onClick={handleClose} title="Close">
          <X size={14} />
        </button>
      </div>
    </header>
  );
};

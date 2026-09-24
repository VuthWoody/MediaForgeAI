import React from 'react';
import {
  LayoutDashboard,
  FolderKanban,
  DownloadCloud,
  Film,
  Languages,
  Layers,
  Settings,
  Terminal,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { useSystem } from '../../context/SystemContext';

export type ActiveModule =
  | 'dashboard'
  | 'projects'
  | 'downloader'
  | 'library'
  | 'studio'
  | 'batch'
  | 'settings'
  | 'logs';

interface SidebarProps {
  activeModule: ActiveModule;
  onSelectModule: (module: ActiveModule) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeModule,
  onSelectModule,
  isCollapsed,
  onToggleCollapse,
}) => {
  const { projects } = useProject();
  const { metrics } = useSystem();

  const navItems: Array<{
    id: ActiveModule;
    label: string;
    icon: React.ReactNode;
    badge?: string | number;
    phaseBadge?: string;
  }> = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <LayoutDashboard className="nav-icon" />,
    },
    {
      id: 'projects',
      label: 'Projects',
      icon: <FolderKanban className="nav-icon" />,
      badge: projects.length,
    },
    {
      id: 'downloader',
      label: 'Downloader',
      icon: <DownloadCloud className="nav-icon" />,
      phaseBadge: 'Phase 2',
    },
    {
      id: 'library',
      label: 'Media Library',
      icon: <Film className="nav-icon" />,
      phaseBadge: 'Phase 2',
    },
    {
      id: 'studio',
      label: 'AI Studio',
      icon: <Languages className="nav-icon" />,
      phaseBadge: 'Phase 3+',
    },
    {
      id: 'batch',
      label: 'Batch Queue',
      icon: <Layers className="nav-icon" />,
      badge: metrics.activeJobsCount > 0 ? metrics.activeJobsCount : undefined,
      phaseBadge: 'Phase 9',
    },
  ];

  const bottomItems: Array<{
    id: ActiveModule;
    label: string;
    icon: React.ReactNode;
  }> = [
    {
      id: 'settings',
      label: 'Settings',
      icon: <Settings className="nav-icon" />,
    },
    {
      id: 'logs',
      label: 'Logs & Diagnostics',
      icon: <Terminal className="nav-icon" />,
    },
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : 'expanded'}`}>
      <div className="sidebar-header">
        {!isCollapsed && (
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
            Workspaces
          </span>
        )}
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = activeModule === item.id;
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectModule(item.id)}
              title={isCollapsed ? item.label : undefined}
            >
              {item.icon}
              {!isCollapsed && <span className="nav-label">{item.label}</span>}
              {!isCollapsed && item.badge !== undefined && (
                <span className="nav-badge">{item.badge}</span>
              )}
              {!isCollapsed && item.phaseBadge && !item.badge && (
                <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', color: 'var(--text-dim)' }}>
                  {item.phaseBadge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        {bottomItems.map((item) => {
          const isActive = activeModule === item.id;
          return (
            <button
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectModule(item.id)}
              title={isCollapsed ? item.label : undefined}
            >
              {item.icon}
              {!isCollapsed && <span className="nav-label">{item.label}</span>}
            </button>
          );
        })}
      </div>
    </aside>
  );
};

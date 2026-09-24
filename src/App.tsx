import React, { useState } from 'react';
import { TitleBar } from './components/layout/TitleBar';
import { Sidebar, ActiveModule } from './components/layout/Sidebar';
import { StatusBar } from './components/layout/StatusBar';
import { DashboardView } from './components/dashboard/DashboardView';
import { ProjectsView } from './components/projects/ProjectsView';
import { DownloaderView } from './components/downloader/DownloaderView';
import { MediaLibraryView } from './components/library/MediaLibraryView';
import { SettingsView } from './components/settings/SettingsView';
import { LogViewerView } from './components/logs/LogViewerView';
import { StudioView } from './components/studio/StudioView';
import { ModuleStub } from './components/modules/ModuleStubs';
import { ProjectProvider } from './context/ProjectContext';
import { SettingsProvider } from './context/SettingsContext';
import { SystemProvider } from './context/SystemContext';
import { DownloaderProvider } from './context/DownloaderContext';
import { MediaLibraryProvider } from './context/MediaLibraryContext';
import { StudioProvider } from './context/StudioContext';

export const AppContent: React.FC = () => {
  const [activeModule, setActiveModule] = useState<ActiveModule>('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="app-container">
      {/* Frameless Title Bar */}
      <TitleBar />

      {/* Main Workspace Body */}
      <div className="app-body">
        <Sidebar
          activeModule={activeModule}
          onSelectModule={setActiveModule}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />

        <main className="main-content">
          {activeModule === 'dashboard' && <DashboardView onNavigate={setActiveModule} />}
          {activeModule === 'projects' && (
            <ProjectsView onOpenInStudio={() => setActiveModule('studio')} />
          )}
          {activeModule === 'downloader' && <DownloaderView />}
          {activeModule === 'library' && (
            <MediaLibraryView onOpenInStudio={() => setActiveModule('studio')} />
          )}
          {activeModule === 'studio' && <StudioView />}
          {activeModule === 'batch' && (
            <ModuleStub module="batch" onNavigate={setActiveModule} />
          )}
          {activeModule === 'settings' && <SettingsView />}
          {activeModule === 'logs' && <LogViewerView />}
        </main>
      </div>

      {/* Telemetry Status Bar */}
      <StatusBar onOpenLogs={() => setActiveModule('logs')} />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <SettingsProvider>
      <SystemProvider>
        <ProjectProvider>
          <DownloaderProvider>
            <MediaLibraryProvider>
              <StudioProvider>
                <AppContent />
              </StudioProvider>
            </MediaLibraryProvider>
          </DownloaderProvider>
        </ProjectProvider>
      </SystemProvider>
    </SettingsProvider>
  );
};

export default App;

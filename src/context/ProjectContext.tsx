import React, { createContext, useContext, useEffect, useState } from 'react';
import { ProjectData, ProjectSummary } from '../types/project';
import { FALLBACK_SAMPLE_PROJECT } from '../utils/sampleProject';

interface ProjectContextType {
  projects: ProjectSummary[];
  activeProject: ProjectData | null;
  isLoading: boolean;
  loadProjects: () => Promise<void>;
  openProject: (id: string) => Promise<ProjectData | null>;
  closeProject: () => void;
  createProject: (data: Partial<ProjectData>) => Promise<ProjectData>;
  updateProject: (project: ProjectData) => Promise<ProjectData>;
  deleteProject: (id: string) => Promise<boolean>;
  duplicateProject: (id: string) => Promise<ProjectData | null>;
  openProjectFolder: (id: string) => Promise<void>;
  selectMediaFile: () => Promise<string | null>;
}

const ProjectContext = createContext<ProjectContextType>({
  projects: [],
  activeProject: null,
  isLoading: true,
  loadProjects: async () => {},
  openProject: async () => null,
  closeProject: () => {},
  createProject: async () => FALLBACK_SAMPLE_PROJECT,
  updateProject: async () => FALLBACK_SAMPLE_PROJECT,
  deleteProject: async () => false,
  duplicateProject: async () => null,
  openProjectFolder: async () => {},
  selectMediaFile: async () => null,
});

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadProjects = async () => {
    setIsLoading(true);
    if (window.electronAPI?.listProjects) {
      try {
        const list = await window.electronAPI.listProjects();
        setProjects(list);
      } catch (err) {
        console.error('Failed to load projects from electron:', err);
      }
    } else {
      // Browser fallback
      const sampleSummary: ProjectSummary = {
        id: FALLBACK_SAMPLE_PROJECT.id,
        name: FALLBACK_SAMPLE_PROJECT.name,
        description: FALLBACK_SAMPLE_PROJECT.description,
        status: FALLBACK_SAMPLE_PROJECT.status,
        progressPercent: FALLBACK_SAMPLE_PROJECT.progressPercent,
        createdAt: FALLBACK_SAMPLE_PROJECT.createdAt,
        updatedAt: FALLBACK_SAMPLE_PROJECT.updatedAt,
        lastOpenedAt: FALLBACK_SAMPLE_PROJECT.lastOpenedAt,
        sourceLanguage: FALLBACK_SAMPLE_PROJECT.sourceLanguage,
        targetLanguage: FALLBACK_SAMPLE_PROJECT.targetLanguage,
        durationSeconds: FALLBACK_SAMPLE_PROJECT.sourceMedia?.durationSeconds || 0,
        projectDirectory: FALLBACK_SAMPLE_PROJECT.projectDirectory,
      };
      setProjects([sampleSummary]);
    }
    setIsLoading(false);
  };

  const openProject = async (id: string): Promise<ProjectData | null> => {
    setIsLoading(true);
    if (window.electronAPI?.getProject) {
      try {
        const proj = await window.electronAPI.getProject(id);
        setActiveProject(proj);
        await loadProjects(); // Refresh lastOpenedAt in summaries
        setIsLoading(false);
        return proj;
      } catch (err) {
        console.error(`Failed to open project ${id}:`, err);
      }
    } else {
      if (id === FALLBACK_SAMPLE_PROJECT.id) {
        setActiveProject(FALLBACK_SAMPLE_PROJECT);
        setIsLoading(false);
        return FALLBACK_SAMPLE_PROJECT;
      }
    }
    setIsLoading(false);
    return null;
  };

  const closeProject = () => {
    setActiveProject(null);
  };

  const createProject = async (data: Partial<ProjectData>): Promise<ProjectData> => {
    if (window.electronAPI?.createProject) {
      const created = await window.electronAPI.createProject(data);
      setActiveProject(created);
      await loadProjects();
      return created;
    } else {
      const id = 'proj-' + Math.random().toString(36).substring(2, 9);
      const newProj: ProjectData = {
        ...FALLBACK_SAMPLE_PROJECT,
        ...data,
        id,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        lastOpenedAt: new Date().toISOString(),
      };
      setActiveProject(newProj);
      await loadProjects();
      return newProj;
    }
  };

  const updateProject = async (project: ProjectData): Promise<ProjectData> => {
    if (window.electronAPI?.updateProject) {
      const updated = await window.electronAPI.updateProject(project);
      setActiveProject(updated);
      await loadProjects();
      return updated;
    } else {
      setActiveProject(project);
      return project;
    }
  };

  const deleteProject = async (id: string): Promise<boolean> => {
    if (window.electronAPI?.deleteProject) {
      const success = await window.electronAPI.deleteProject(id);
      if (success) {
        if (activeProject?.id === id) {
          setActiveProject(null);
        }
        await loadProjects();
      }
      return success;
    } else {
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (activeProject?.id === id) setActiveProject(null);
      return true;
    }
  };

  const duplicateProject = async (id: string): Promise<ProjectData | null> => {
    if (window.electronAPI?.duplicateProject) {
      try {
        const duplicated = await window.electronAPI.duplicateProject(id);
        await loadProjects();
        return duplicated;
      } catch (err) {
        console.error('Failed to duplicate project:', err);
        return null;
      }
    }
    return null;
  };

  const openProjectFolder = async (id: string): Promise<void> => {
    if (window.electronAPI?.openProjectFolder) {
      await window.electronAPI.openProjectFolder(id);
    }
  };

  const selectMediaFile = async (): Promise<string | null> => {
    if (window.electronAPI?.selectMediaFile) {
      const result = await window.electronAPI.selectMediaFile();
      if (!result.canceled && result.filePath) {
        return result.filePath;
      }
    }
    return null;
  };

  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        isLoading,
        loadProjects,
        openProject,
        closeProject,
        createProject,
        updateProject,
        deleteProject,
        duplicateProject,
        openProjectFolder,
        selectMediaFile,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => useContext(ProjectContext);

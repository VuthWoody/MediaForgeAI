import React, { useState } from 'react';
import {
  FolderKanban,
  Plus,
  Search,
  LayoutGrid,
  List,
  FolderOpen,
  Copy,
  Trash2,
  Play,
  Languages,
  Clock,
  Sparkles,
  Layers,
  ExternalLink,
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { ProjectSummary, ProjectStatus } from '../../types/project';
import { formatDuration, formatDate, getLanguageName } from '../../utils/formatters';
import { NewProjectModal } from './NewProjectModal';
import { Modal } from '../common/Modal';

interface ProjectsViewProps {
  onOpenInStudio?: (id: string) => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({ onOpenInStudio }) => {
  const {
    projects,
    activeProject,
    openProject,
    deleteProject,
    duplicateProject,
    openProjectFolder,
  } = useProject();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null);

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleOpen = async (id: string) => {
    await openProject(id);
    if (onOpenInStudio) {
      onOpenInStudio(id);
    }
  };

  const handleDuplicate = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await duplicateProject(id);
  };

  const handleOpenFolder = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await openProjectFolder(id);
  };

  const confirmDelete = async () => {
    if (projectToDelete) {
      await deleteProject(projectToDelete);
      setProjectToDelete(null);
    }
  };

  return (
    <div className="projects-container">
      {/* Header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FolderKanban size={26} color="var(--cyan)" />
            <span>Projects Studio</span>
            <span className="badge badge-cyan">{projects.length} Total</span>
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Manage video translation sessions, subtitles, dubbed audio tracks, and project archives.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="btn btn-primary" onClick={() => setIsNewModalOpen(true)}>
            <Plus size={16} />
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* Filter and Search controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          marginBottom: '24px',
          background: 'var(--bg-surface)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--glass-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
          {/* Search box */}
          <div style={{ position: 'relative', width: '280px' }}>
            <Search
              size={15}
              style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: '100%', paddingLeft: '34px' }}
            />
          </div>

          {/* Status filters */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {['all', 'draft', 'transcribed', 'translated', 'dubbed', 'completed'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`btn btn-sm ${statusFilter === status ? 'btn-primary' : 'btn-ghost'}`}
                style={{ textTransform: 'capitalize', fontSize: '11px' }}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        {/* View toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-deepest)', padding: '3px', borderRadius: 'var(--radius-sm)' }}>
          <button
            className={`btn btn-ghost btn-sm ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
            title="Grid View"
            style={{ padding: '6px 8px', color: viewMode === 'grid' ? 'var(--cyan)' : 'var(--text-muted)' }}
          >
            <LayoutGrid size={15} />
          </button>
          <button
            className={`btn btn-ghost btn-sm ${viewMode === 'list' ? 'active' : ''}`}
            onClick={() => setViewMode('list')}
            title="List View"
            style={{ padding: '6px 8px', color: viewMode === 'list' ? 'var(--cyan)' : 'var(--text-muted)' }}
          >
            <List size={15} />
          </button>
        </div>
      </div>

      {/* Projects Display */}
      {filteredProjects.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <FolderKanban size={48} style={{ margin: '0 auto 16px auto', opacity: 0.3 }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            No projects matched your criteria
          </h3>
          <p style={{ fontSize: '13px', marginBottom: '16px' }}>
            Create a new project or adjust your search filter.
          </p>
          <button className="btn btn-primary btn-sm" onClick={() => setIsNewModalOpen(true)}>
            <Plus size={14} />
            <span>Create New Project</span>
          </button>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="projects-grid">
          {filteredProjects.map((proj) => {
            const isActive = activeProject?.id === proj.id;
            return (
              <div
                key={proj.id}
                className="project-card"
                onClick={() => handleOpen(proj.id)}
                style={{
                  borderColor: isActive ? 'var(--cyan)' : undefined,
                  boxShadow: isActive ? 'var(--cyan-glow)' : undefined,
                }}
              >
                {/* Thumbnail / Header Area */}
                <div className="project-thumbnail">
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <Play size={32} color="var(--cyan)" style={{ opacity: 0.8 }} />
                    <span style={{ fontSize: '11px', fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)' }}>
                      {proj.sourceLanguage.toUpperCase()} → {proj.targetLanguage.toUpperCase()}
                    </span>
                  </div>
                  <div className="project-duration-badge">
                    {formatDuration(proj.durationSeconds)}
                  </div>
                  {isActive && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '10px',
                        left: '10px',
                        background: 'var(--cyan)',
                        color: '#050811',
                        fontWeight: 700,
                        fontSize: '10px',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        letterSpacing: '0.5px',
                        textTransform: 'uppercase',
                      }}
                    >
                      Active
                    </div>
                  )}
                </div>

                {/* Project Details */}
                <div className="project-content">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h3 className="project-title" title={proj.name}>
                      {proj.name}
                    </h3>
                    <span className="badge badge-violet" style={{ fontSize: '10px' }}>
                      {proj.status}
                    </span>
                  </div>

                  <p className="project-desc">
                    {proj.description || 'No project description provided.'}
                  </p>

                  <div className="project-meta-row">
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} />
                      <span>{formatDate(proj.updatedAt)}</span>
                    </span>
                    <span style={{ color: 'var(--text-cyan)', fontWeight: 600 }}>
                      {getLanguageName(proj.targetLanguage)}
                    </span>
                  </div>

                  {/* Actions Footer */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      gap: '6px',
                      paddingTop: '8px',
                      marginTop: '4px',
                      borderTop: '1px solid var(--glass-border-subtle)',
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => handleOpenFolder(e, proj.id)}
                      title="Reveal in Windows Explorer"
                    >
                      <FolderOpen size={14} />
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={(e) => handleDuplicate(e, proj.id)}
                      title="Duplicate Project"
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => setProjectToDelete(proj.id)}
                      title="Delete Project"
                      style={{ color: 'var(--rose)' }}
                    >
                      <Trash2 size={14} />
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpen(proj.id)}
                      style={{ marginLeft: '4px' }}
                    >
                      Open
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View */
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--glass-border)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Project Name</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Language Pair</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Duration</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Last Modified</th>
                <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((proj) => (
                <tr
                  key={proj.id}
                  onClick={() => handleOpen(proj.id)}
                  style={{
                    borderBottom: '1px solid var(--glass-border-subtle)',
                    cursor: 'pointer',
                    transition: 'background var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {proj.name}
                  </td>
                  <td style={{ padding: '14px 16px', color: 'var(--text-cyan)' }}>
                    {getLanguageName(proj.sourceLanguage)} → {getLanguageName(proj.targetLanguage)}
                  </td>
                  <td style={{ padding: '14px 16px', fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)' }}>
                    {formatDuration(proj.durationSeconds)}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <span className="badge badge-violet">{proj.status}</span>
                  </td>
                  <td style={{ padding: '14px 16px', color: 'var(--text-muted)' }}>
                    {formatDate(proj.updatedAt)}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'inline-flex', gap: '6px' }}>
                      <button className="btn btn-ghost btn-sm" onClick={(e) => handleOpenFolder(e, proj.id)} title="Open Folder">
                        <FolderOpen size={14} />
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={(e) => handleDuplicate(e, proj.id)} title="Duplicate">
                        <Copy size={14} />
                      </button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setProjectToDelete(proj.id)} style={{ color: 'var(--rose)' }} title="Delete">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onCreated={(p) => {
          setIsNewModalOpen(false);
          handleOpen(p.id);
        }}
      />

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!projectToDelete}
        onClose={() => setProjectToDelete(null)}
        title="Delete Project?"
        subtitle="This action will permanently delete the project and all cached stems from disk."
        maxWidth="440px"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setProjectToDelete(null)}>
              Cancel
            </button>
            <button className="btn btn-danger" onClick={confirmDelete}>
              <Trash2 size={14} />
              <span>Confirm Delete</span>
            </button>
          </>
        }
      >
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          Are you sure you want to delete this project? This cannot be undone.
        </p>
      </Modal>
    </div>
  );
};

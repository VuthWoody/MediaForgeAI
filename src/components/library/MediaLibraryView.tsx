import React, { useState } from 'react';
import {
  Film,
  FolderOpen,
  Search,
  LayoutGrid,
  List,
  Sparkles,
  Play,
  Trash2,
  ExternalLink,
  Plus,
  Info,
  Clock,
  HardDrive,
  Globe,
} from 'lucide-react';
import { useMediaLibrary } from '../../context/MediaLibraryContext';
import { useProject } from '../../context/ProjectContext';
import { MediaLibraryItem } from '../../types/mediaLibrary';
import { formatBytes, formatDuration, formatDate } from '../../utils/formatters';
import { Modal } from '../common/Modal';

interface MediaLibraryViewProps {
  onOpenInStudio: (projectId: string) => void;
}

export const MediaLibraryView: React.FC<MediaLibraryViewProps> = ({ onOpenInStudio }) => {
  const {
    items,
    selectedItem,
    filters,
    isLoading,
    setFilters,
    selectItem,
    importFile,
    deleteMedia,
    createStudioProject,
  } = useMediaLibrary();

  const { openProject } = useProject();

  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [inspectItem, setInspectItem] = useState<MediaLibraryItem | null>(null);
  const [itemToDelete, setItemToDelete] = useState<MediaLibraryItem | null>(null);

  const platforms = [
    { id: 'all', label: 'All Media' },
    { id: 'youtube', label: 'YouTube' },
    { id: 'tiktok', label: 'TikTok' },
    { id: 'facebook', label: 'Facebook' },
    { id: 'twitter', label: 'Twitter / X' },
    { id: 'custom', label: 'Local Imports' },
  ];

  const handleLaunchStudio = async (mediaId: string) => {
    const project = await createStudioProject(mediaId);
    if (project) {
      await openProject(project.id);
      onOpenInStudio(project.id);
    }
  };

  const confirmDelete = async () => {
    if (itemToDelete) {
      await deleteMedia(itemToDelete.id, false);
      setItemToDelete(null);
    }
  };

  return (
    <div className="media-library-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'Outfit, sans-serif', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Film size={26} color="var(--emerald)" />
            <span>Media Library & Asset Manager</span>
            <span className="badge badge-emerald">{items.length} Assets</span>
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Organized catalog of downloaded web media and imported local video assets ready for AI processing.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button className="btn btn-primary" onClick={() => importFile()}>
            <Plus size={16} />
            <span>Import Local Video</span>
          </button>
        </div>
      </div>

      {/* Main Layout: Filter Rail + Media Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '20px', alignItems: 'start' }}>
        {/* Left Platform Filter Sidebar */}
        <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: '8px', paddingLeft: '8px' }}>
            Platforms
          </span>
          {platforms.map((p) => {
            const count =
              p.id === 'all'
                ? items.length
                : items.filter((i) => i.platform.toLowerCase() === p.id.toLowerCase()).length;
            const isSelected = (filters.platform || 'all') === p.id;
            return (
              <button
                key={p.id}
                onClick={() => setFilters({ ...filters, platform: p.id })}
                className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-ghost'}`}
                style={{
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12px',
                }}
              >
                <span>{p.label}</span>
                <span style={{ fontSize: '10px', opacity: 0.8, background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '10px' }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Right Content Area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Search and Sort Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              background: 'var(--bg-surface)',
              padding: '10px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--glass-border)',
            }}
          >
            <div style={{ position: 'relative', width: '280px' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                className="input-field"
                placeholder="Search by title, creator, tag..."
                value={filters.searchQuery || ''}
                onChange={(e) => setFilters({ ...filters, searchQuery: e.target.value })}
                style={{ width: '100%', paddingLeft: '32px', height: '34px', fontSize: '12px' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <select
                className="select-field"
                value={filters.sortBy}
                onChange={(e) => setFilters({ ...filters, sortBy: e.target.value as any })}
                style={{ height: '34px', fontSize: '12px', padding: '4px 10px' }}
              >
                <option value="date-desc">Newest First</option>
                <option value="date-asc">Oldest First</option>
                <option value="duration-desc">Longest Duration</option>
                <option value="size-desc">Largest Size</option>
                <option value="title">Alphabetical (Title)</option>
              </select>

              <div style={{ display: 'flex', background: 'var(--bg-deepest)', padding: '3px', borderRadius: 'var(--radius-sm)' }}>
                <button
                  className={`btn btn-ghost btn-sm ${viewMode === 'grid' ? 'active' : ''}`}
                  onClick={() => setViewMode('grid')}
                  style={{ padding: '6px 8px', color: viewMode === 'grid' ? 'var(--cyan)' : 'var(--text-muted)' }}
                >
                  <LayoutGrid size={14} />
                </button>
                <button
                  className={`btn btn-ghost btn-sm ${viewMode === 'list' ? 'active' : ''}`}
                  onClick={() => setViewMode('list')}
                  style={{ padding: '6px 8px', color: viewMode === 'list' ? 'var(--cyan)' : 'var(--text-muted)' }}
                >
                  <List size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Media Items Presentation */}
          {items.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <Film size={44} style={{ margin: '0 auto 14px auto', opacity: 0.3 }} />
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
                No media in library
              </h3>
              <p style={{ fontSize: '13px', marginBottom: '16px' }}>
                Download videos from the Downloader or import local files.
              </p>
              <button className="btn btn-primary btn-sm" onClick={() => importFile()}>
                <Plus size={14} />
                <span>Import First Video</span>
              </button>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="projects-grid">
              {items.map((item) => (
                <div key={item.id} className="project-card" onClick={() => setInspectItem(item)}>
                  {/* Thumbnail */}
                  <div className="project-thumbnail">
                    {item.thumbnailPath ? (
                      <img src={`file://${item.thumbnailPath}`} alt={item.title} />
                    ) : (
                      <Film size={34} color="var(--emerald)" style={{ opacity: 0.7 }} />
                    )}
                    <div className="project-duration-badge">
                      {formatDuration(item.durationSeconds)}
                    </div>
                    <div
                      style={{
                        position: 'absolute',
                        top: '10px',
                        left: '10px',
                        background: 'rgba(0, 0, 0, 0.75)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontFamily: 'JetBrains Mono',
                        color: 'var(--text-cyan)',
                        textTransform: 'uppercase',
                      }}
                    >
                      {item.resolution.width > 0 ? `${item.resolution.height}p` : 'Audio'}
                    </div>
                  </div>

                  {/* Card Content */}
                  <div className="project-content">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <h3 className="project-title" title={item.title}>
                        {item.title}
                      </h3>
                      <span className="badge badge-emerald" style={{ fontSize: '10px' }}>
                        {item.platform}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      Creator: <span style={{ color: 'var(--text-secondary)' }}>{item.creator}</span>
                    </div>

                    <div className="project-meta-row">
                      <span>{formatBytes(item.fileSizeBytes)}</span>
                      <span>{formatDate(item.importedAt)}</span>
                    </div>

                    {/* Action Bar with Studio Bridge Button */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        paddingTop: '8px',
                        marginTop: '4px',
                        borderTop: '1px solid var(--glass-border-subtle)',
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => window.electronAPI?.showItemInFolder?.(item.filePath)}
                          title="Show file in Explorer"
                        >
                          <FolderOpen size={14} />
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setInspectItem(item)}
                          title="Technical Stream Info"
                        >
                          <Info size={14} />
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setItemToDelete(item)}
                          style={{ color: 'var(--rose)' }}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>

                      {/* 1-Click Studio Bridge */}
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleLaunchStudio(item.id)}
                        title="Send this video to AI Translation & Dubbing Studio"
                      >
                        <Sparkles size={13} />
                        <span>Studio</span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* List View */
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--glass-border)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '12px 16px' }}>Title</th>
                    <th style={{ padding: '12px 16px' }}>Platform</th>
                    <th style={{ padding: '12px 16px' }}>Creator</th>
                    <th style={{ padding: '12px 16px' }}>Duration</th>
                    <th style={{ padding: '12px 16px' }}>Resolution</th>
                    <th style={{ padding: '12px 16px' }}>Size</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      style={{ borderBottom: '1px solid var(--glass-border-subtle)', cursor: 'pointer' }}
                      onClick={() => setInspectItem(item)}
                    >
                      <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {item.title}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span className="badge badge-emerald">{item.platform}</span>
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                        {item.creator}
                      </td>
                      <td style={{ padding: '12px 16px', fontFamily: 'JetBrains Mono' }}>
                        {formatDuration(item.durationSeconds)}
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-cyan)' }}>
                        {item.resolution.width}x{item.resolution.height}
                      </td>
                      <td style={{ padding: '12px 16px', fontFamily: 'JetBrains Mono' }}>
                        {formatBytes(item.fileSizeBytes)}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleLaunchStudio(item.id)}
                            title="Open in Studio"
                          >
                            <Sparkles size={13} />
                            <span>Studio</span>
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => window.electronAPI?.showItemInFolder?.(item.filePath)}
                            title="Show in Explorer"
                          >
                            <FolderOpen size={14} />
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setItemToDelete(item)}
                            style={{ color: 'var(--rose)' }}
                            title="Delete"
                          >
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
        </div>
      </div>

      {/* Media Technical Inspector Modal */}
      <Modal
        isOpen={!!inspectItem}
        onClose={() => setInspectItem(null)}
        title={inspectItem?.title || 'Media Stream Metadata'}
        subtitle={`Location: ${inspectItem?.filePath}`}
        maxWidth="580px"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setInspectItem(null)}>
              Close
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                if (inspectItem) {
                  handleLaunchStudio(inspectItem.id);
                  setInspectItem(null);
                }
              }}
            >
              <Sparkles size={14} />
              <span>Bridge to AI Studio</span>
            </button>
          </>
        }
      >
        {inspectItem && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'var(--bg-deepest)', padding: '12px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Resolution</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {inspectItem.resolution.width} x {inspectItem.resolution.height} ({inspectItem.fps} fps)
                </div>
              </div>

              <div style={{ background: 'var(--bg-deepest)', padding: '12px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Video Codec</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', textTransform: 'uppercase' }}>
                  {inspectItem.codec}
                </div>
              </div>

              <div style={{ background: 'var(--bg-deepest)', padding: '12px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Audio Audio Sample Rate</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {inspectItem.audioSampleRate} Hz ({inspectItem.audioChannels} Channels)
                </div>
              </div>

              <div style={{ background: 'var(--bg-deepest)', padding: '12px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>File Size</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {formatBytes(inspectItem.fileSizeBytes)}
                </div>
              </div>
            </div>

            <div style={{ background: 'var(--bg-deepest)', padding: '12px', borderRadius: '6px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Full Path</span>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', wordBreak: 'break-all' }}>
                {inspectItem.filePath}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!itemToDelete}
        onClose={() => setItemToDelete(null)}
        title="Delete Media Asset?"
        subtitle="Remove this media item from your local library catalog."
        maxWidth="420px"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setItemToDelete(null)}>
              Cancel
            </button>
            <button className="btn btn-danger" onClick={confirmDelete}>
              <Trash2 size={14} />
              <span>Delete from Library</span>
            </button>
          </>
        }
      >
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
          Are you sure you want to remove "{itemToDelete?.title}" from your library?
        </p>
      </Modal>
    </div>
  );
};

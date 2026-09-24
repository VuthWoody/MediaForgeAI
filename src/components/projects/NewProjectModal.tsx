import React, { useState } from 'react';
import { FolderOpen, Sparkles, FileVideo, Globe, ShieldCheck } from 'lucide-react';
import { Modal } from '../common/Modal';
import { ProjectData } from '../../types/project';
import { useProject } from '../../context/ProjectContext';

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (project: ProjectData) => void;
}

export const NewProjectModal: React.FC<NewProjectModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const { createProject, selectMediaFile } = useProject();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguage, setTargetLanguage] = useState('km');
  const [mediaPath, setMediaPath] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSelectFile = async () => {
    const file = await selectMediaFile();
    if (file) {
      setMediaPath(file);
      if (!name) {
        const basename = file.split(/[\\/]/).pop() || '';
        setName(basename.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    try {
      const filename = mediaPath ? mediaPath.split(/[\\/]/).pop() || '' : '';
      const newProj = await createProject({
        name: name.trim(),
        description: description.trim(),
        sourceLanguage,
        targetLanguage,
        sourceMedia: mediaPath
          ? {
              type: 'file',
              pathOrUrl: mediaPath,
              filename,
              durationSeconds: 120, // Initial estimate before probe
              resolution: { width: 1920, height: 1080 },
              fps: 30,
              fileSizeBytes: 0,
              codec: 'h264',
              audioSampleRate: 48000,
              audioChannels: 2,
            }
          : undefined,
      });

      setName('');
      setDescription('');
      setMediaPath('');
      onCreated(newProj);
    } catch (err) {
      console.error('Failed to create project:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Studio Project"
      subtitle="Configure project parameters, source media, and target languages."
      maxWidth="640px"
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!name.trim() || isSubmitting}
          >
            <Sparkles size={15} />
            <span>{isSubmitting ? 'Creating Project...' : 'Initialize Project'}</span>
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        {/* Project Name */}
        <div className="input-group">
          <label className="input-label">Project Title *</label>
          <input
            type="text"
            className="input-field"
            placeholder="e.g. AI Technology Keynote 2026"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />
        </div>

        {/* Project Description */}
        <div className="input-group">
          <label className="input-label">Project Description (Optional)</label>
          <input
            type="text"
            className="input-field"
            placeholder="Short summary of this translation and dubbing session"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Source Media Selection */}
        <div className="input-group">
          <label className="input-label">Source Video / Media File</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              className="input-field"
              placeholder="No file selected (can import later)"
              value={mediaPath}
              onChange={(e) => setMediaPath(e.target.value)}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleSelectFile}
              title="Browse computer for media file"
            >
              <FolderOpen size={16} />
              <span>Browse</span>
            </button>
          </div>
        </div>

        {/* Language Selection Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div className="input-group">
            <label className="input-label">Source Audio Language</label>
            <select
              className="select-field"
              value={sourceLanguage}
              onChange={(e) => setSourceLanguage(e.target.value)}
            >
              <option value="en">English (US/UK)</option>
              <option value="zh">Chinese (Mandarin / 中文)</option>
              <option value="ja">Japanese (日本語)</option>
              <option value="ko">Korean (한국어)</option>
              <option value="km">Khmer (ភាសាខ្មែរ)</option>
              <option value="es">Spanish (Español)</option>
              <option value="fr">French (Français)</option>
              <option value="de">German (Deutsch)</option>
            </select>
          </div>

          <div className="input-group">
            <label className="input-label">Target Dubbing / Subtitle Language</label>
            <select
              className="select-field"
              value={targetLanguage}
              onChange={(e) => setTargetLanguage(e.target.value)}
            >
              <option value="km">Khmer (ភាសាខ្មែរ) — Primary</option>
              <option value="en">English</option>
              <option value="zh">Chinese (中文)</option>
              <option value="ja">Japanese (日本語)</option>
              <option value="ko">Korean (한국어)</option>
              <option value="es">Spanish (Español)</option>
              <option value="fr">French (Français)</option>
              <option value="de">German (Deutsch)</option>
            </select>
          </div>
        </div>

        {/* Feature Notice */}
        <div
          style={{
            padding: '12px 14px',
            background: 'rgba(0, 240, 255, 0.05)',
            border: '1px solid rgba(0, 240, 255, 0.18)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
          }}
        >
          <ShieldCheck size={18} color="var(--cyan)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            The project workspace stores original media, isolated vocal/music stems, synchronized Whisper transcripts, AI dubbing voice tracks, and rendered output safely on your local drive.
          </span>
        </div>
      </form>
    </Modal>
  );
};

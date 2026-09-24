import React, { useState } from 'react';
import { Layers, DownloadCloud, Plus } from 'lucide-react';
import { Modal } from '../common/Modal';

interface BulkImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (urls: string[]) => void;
}

export const BulkImportModal: React.FC<BulkImportModalProps> = ({
  isOpen,
  onClose,
  onImport,
}) => {
  const [urlsText, setUrlsText] = useState('');

  const handleImport = () => {
    const urls = urlsText
      .split('\n')
      .map((u) => u.trim())
      .filter((u) => u.startsWith('http://') || u.startsWith('https://'));

    if (urls.length > 0) {
      onImport(urls);
      setUrlsText('');
      onClose();
    }
  };

  const parsedUrlsCount = urlsText
    .split('\n')
    .map((u) => u.trim())
    .filter((u) => u.startsWith('http://') || u.startsWith('https://')).length;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Bulk Media URL Importer"
      subtitle="Queue multiple URLs for batch downloading simultaneously."
      maxWidth="600px"
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleImport}
            disabled={parsedUrlsCount === 0}
          >
            <DownloadCloud size={16} />
            <span>Queue {parsedUrlsCount} Downloads</span>
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Paste video or audio links below (one URL per line). They will be added to the multi-worker download queue automatically.
        </p>

        <textarea
          className="input-field"
          rows={8}
          placeholder="https://www.youtube.com/watch?v=...&#10;https://www.tiktok.com/@creator/video/...&#10;https://vimeo.com/..."
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          style={{ width: '100%', resize: 'vertical', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span>Supported: YouTube, TikTok, Facebook, Twitter/X, Bilibili, Instagram, Vimeo</span>
          <span style={{ color: 'var(--text-cyan)', fontWeight: 600 }}>{parsedUrlsCount} Valid URLs detected</span>
        </div>
      </div>
    </Modal>
  );
};

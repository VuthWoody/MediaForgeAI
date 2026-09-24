const http = require('http');
const { spawn } = require('child_process');

function waitForVite() {
  const req = http.get('http://localhost:5173', (res) => {
    console.log('[MediaForge AI] Vite dev server is ready. Launching Electron desktop shell...');
    const electronProcess = spawn('npx', ['electron', '.'], {
      stdio: 'inherit',
      shell: true,
      env: { ...process.env, NODE_ENV: 'development' },
    });

    electronProcess.on('close', (code) => {
      process.exit(code || 0);
    });
  });

  req.on('error', () => {
    setTimeout(waitForVite, 400);
  });
}

console.log('[MediaForge AI] Waiting for Vite development server to start on port 5173...');
waitForVite();

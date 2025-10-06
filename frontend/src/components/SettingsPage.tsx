'use client';

import { useState, useEffect } from 'react';
import { api } from '@/server_api/client';
import type { ConfigResponse } from '@/server_api/generated/models';

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [originalConfig, setOriginalConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const configData = await api.getConfig();
      setConfig(configData as ConfigResponse);
      setOriginalConfig(JSON.parse(JSON.stringify(configData)));
    } catch {
      setError('Unable to fetch configuration. Make sure the API server is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;

    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await api.saveConfig({ configResponse: config as ConfigResponse });
      setOriginalConfig(JSON.parse(JSON.stringify(config)));
      
      // Handle different response types based on reload success
      if (result.reloaded === true) {
        setSuccessMessage(result.message || 'Configuration saved and reloaded successfully! Changes are now active.');
      } else if (result.reloaded === false) {
        setSuccessMessage(result.message || 'Configuration saved, but hot-reload failed. Please restart the server to apply changes.');
      } else {
        setSuccessMessage(result.message || 'Configuration saved successfully!');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (originalConfig) {
      setConfig(JSON.parse(JSON.stringify(originalConfig)));
      setError(null);
      setSuccessMessage(null);
    }
  };

  const hasChanges = () => {
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  };

  const updateConfig = <K extends keyof ConfigResponse, P extends keyof ConfigResponse[K]>(
    section: K,
    key: P,
    value: ConfigResponse[K][P]
  ) => {
    if (!config) return;

    setConfig((prev) =>
      prev
        ? ({
            ...prev,
            [section]: {
              ...(prev[section] as ConfigResponse[K]),
              [key]: value,
            },
          } as ConfigResponse)
        : prev
    );
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          ⚙️ Settings
        </h2>
        <div className="animate-pulse space-y-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-gray-200 dark:bg-gray-700 h-20 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <div className="p-6 border-b border-gray-200 dark:border-gray-600">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          ⚙️ Settings
        </h2>
        <p className="text-gray-600 dark:text-gray-300">
          Configure your Mycelium server installation. Changes require a server restart.
        </p>
      </div>

      <div className="p-6 space-y-8">
        {error && (
          <div className="bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {successMessage && (
          <div className="bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-700 rounded-lg p-4">
            <p className="text-green-700 dark:text-green-300">{successMessage}</p>
          </div>
        )}

        {config && (
          <>
            {/* Media Server Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🎵 Media Server
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Media Server Type
                  </label>
                  <select
                    value={config.media_server.type}
                    onChange={(e) => updateConfig('media_server', 'type', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="plex">Plex Media Server</option>
                    <option value="jellyfin">Jellyfin (Coming Soon)</option>
                  </select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Choose your preferred media server platform
                  </p>
                </div>
              </div>
            </div>

            {/* Plex Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                📺 Plex Server
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server URL
                  </label>
                  <input
                    type="text"
                    value={config.plex.url}
                    onChange={(e) => updateConfig('plex', 'url', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="http://localhost:32400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Music Library Name
                  </label>
                  <input
                    type="text"
                    value={config.plex.music_library_name}
                    onChange={(e) => updateConfig('plex', 'music_library_name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Music"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Plex Token
                  </label>
                  <input
                    type="password"
                    value={config.plex.token ?? ''}
                    onChange={(e) => updateConfig('plex', 'token', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="Your Plex authentication token"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Get your token from{' '}
                    <a href="https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/"
                       target="_blank" rel="noopener noreferrer"
                       className="text-purple-600 dark:text-purple-400 hover:underline">
                      Plex support
                    </a>
                  </p>
                </div>
              </div>
            </div>

            {/* API Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🌐 API Server
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Host
                  </label>
                  <input
                    type="text"
                    value={config.api.host}
                    onChange={(e) => updateConfig('api', 'host', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Port
                  </label>
                  <input
                    type="number"
                    value={config.api.port}
                    onChange={(e) => updateConfig('api', 'port', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
                <div className="flex items-center">
                  <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                    <input
                      type="checkbox"
                      checked={config.api.reload}
                      onChange={(e) => updateConfig('api', 'reload', e.target.checked)}
                      className="rounded border-gray-300 dark:border-gray-600"
                    />
                    <span>Auto-reload</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Server Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🖥️ Server
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    GPU Batch Size
                  </label>
                  <input
                    type="number"
                    value={config.server.gpu_batch_size}
                    onChange={(e) => updateConfig('server', 'gpu_batch_size', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    min="1"
                    max="64"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Batch size for distributed GPU workers
                  </p>
                </div>
              </div>
            </div>

            {/* CLAP Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🧠 AI Model (CLAP)
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Model ID
                  </label>
                  <select
                    value={config.clap.model_id}
                    onChange={(e) => updateConfig('clap', 'model_id', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="laion/larger_clap_music_and_speech">CLAP Music & Speech (Recommended)</option>
                    <option value="laion/larger_clap_music">CLAP Music (If your library is mostly instrumental/electronic)</option>
                    <option value="laion/clap-htsat-unfused">CLAP HTSAT Unfused (Trained with general sounds, not only music)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Sample Rate
                  </label>
                  <input
                    type="number"
                    value={config.clap.target_sr}
                    onChange={(e) => updateConfig('clap', 'target_sr', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Chunk Duration (s)
                  </label>
                  <input
                    type="number"
                    value={config.clap.chunk_duration_s}
                    onChange={(e) => updateConfig('clap', 'chunk_duration_s', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    min="1"
                    max="30"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Number of Chunks
                  </label>
                  <input
                    type="number"
                    value={config.clap.num_chunks}
                    onChange={(e) => updateConfig('clap', 'num_chunks', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    min="1"
                    max="10"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Number of audio chunks to extract per track
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Max Load Duration (s)
                  </label>
                  <input
                    type="number"
                    value={config.clap.max_load_duration_s ?? 0}
                    onChange={(e) => updateConfig('clap', 'max_load_duration_s', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    min="10"
                    max="600"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Maximum seconds of audio to load per track
                  </p>
                </div>
              </div>
            </div>

            {/* Database Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🗄️ Database
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Collection Name
                  </label>
                  <input
                    type="text"
                    value={config.chroma.collection_name}
                    onChange={(e) => updateConfig('chroma', 'collection_name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Batch Size
                  </label>
                  <input
                    type="number"
                    value={config.chroma.batch_size}
                    onChange={(e) => updateConfig('chroma', 'batch_size', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>
              </div>
            </div>

            {/* Logging Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                📝 Logging
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Log Level
                  </label>
                  <select
                    value={config.logging.level}
                    onChange={(e) => updateConfig('logging', 'level', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between items-center pt-6 border-t border-gray-200 dark:border-gray-600">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Configuration is stored in ~/.config/mycelium/config.yml
              </div>
              <div className="space-x-3">
                <button
                  onClick={handleReset}
                  disabled={!hasChanges() || saving}
                  className="px-4 py-2 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Reset
                </button>
                <button
                  onClick={handleSave}
                  disabled={!hasChanges() || saving}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
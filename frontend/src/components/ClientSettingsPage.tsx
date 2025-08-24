'use client';

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

interface ClientConfigData {
  client: {
    server_host: string;
    server_port: number;
  };
  client_api: {
    host: string;
    port: number;
  };
  clap: {
    model_id: string;
    target_sr: number;
    chunk_duration_s: number;
  };
  logging: {
    level: string;
  };
}

export default function ClientSettingsPage() {
  const [config, setConfig] = useState<ClientConfigData | null>(null);
  const [originalConfig, setOriginalConfig] = useState<ClientConfigData | null>(null);
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
      const response = await fetch(`${API_BASE_URL}/api/config`);
      if (!response.ok) {
        throw new Error('Failed to fetch configuration');
      }
      const configData = await response.json();
      const clientConfig: ClientConfigData = {
        client: configData.client,
        client_api: configData.client_api,
        clap: configData.clap,
        logging: configData.logging
      };
      setConfig(clientConfig);
      setOriginalConfig(JSON.parse(JSON.stringify(clientConfig)));
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
      const currentResponse = await fetch(`${API_BASE_URL}/api/config`);
      if (!currentResponse.ok) {
        throw new Error('Failed to fetch current configuration');
      }

      const updatedConfig = {
        client: config.client,
        client_api: config.client_api,
        clap: config.clap,
        logging: config.logging
      };

      const response = await fetch(`${API_BASE_URL}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedConfig)
      });

      if (!response.ok) {
        throw new Error('Failed to save configuration');
      }

      const result = await response.json();
      setOriginalConfig(JSON.parse(JSON.stringify(config)));

      setSuccessMessage(result.message || 'Configuration saved successfully!');
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

  const updateConfig = (section: keyof ClientConfigData, key: string, value: string | number | boolean) => {
    if (!config) return;

    setConfig(prev => ({
      ...prev!,
      [section]: {
        ...prev![section],
        [key]: value
      }
    }));
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          ⚙️ Client Settings
        </h2>
        <div className="animate-pulse space-y-4">
          {[...Array(3)].map((_, i) => (
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
          ⚙️ Client Settings
        </h2>
        <p className="text-gray-600 dark:text-gray-300">
          Configure your Mycelium client worker. Changes are applied immediately with hot-reload.
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
            {/* Client Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🖥️ Client Worker
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server Host
                  </label>
                  <input
                    type="text"
                    value={config.client.server_host}
                    onChange={(e) => updateConfig('client', 'server_host', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server Port
                  </label>
                  <input
                    type="number"
                    value={config.client.server_port}
                    onChange={(e) => updateConfig('client', 'server_port', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="8000"
                  />
                </div>
              </div>
            </div>

            {/* Client API Server Configuration */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                🔌 Client API Server
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Configure the local API server for client configuration management.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API Host
                  </label>
                  <input
                    type="text"
                    value={config.client_api.host}
                    onChange={(e) => updateConfig('client_api', 'host', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API Port
                  </label>
                  <input
                    type="number"
                    value={config.client_api.port}
                    onChange={(e) => updateConfig('client_api', 'port', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    placeholder="3001"
                  />
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
                Configuration is stored in ~/.config/mycelium/client_config.yml
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
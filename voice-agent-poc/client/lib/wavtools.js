/**
 * WavTools - Audio utilities for voice agent
 * Based on LiveKit patterns for low-latency streaming
 */

/**
 * WavRecorder - Captures microphone audio as PCM16 @ 24kHz
 */
export class WavRecorder {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 24000;
    this.stream = null;
    this.audioContext = null;
    this.source = null;
    this.processor = null;
    this.recording = false;
    this.onDataCallback = null;
  }

  /**
   * Request microphone access and initialize audio context
   */
  async begin() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      this.audioContext = new AudioContext({ sampleRate: this.sampleRate });
      this.source = this.audioContext.createMediaStreamSource(this.stream);

      // Create script processor for raw audio access
      // Note: ScriptProcessorNode is deprecated but works reliably
      // For production, use AudioWorklet
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.processor.onaudioprocess = (event) => {
        if (this.recording && this.onDataCallback) {
          const inputData = event.inputBuffer.getChannelData(0);
          // Convert Float32 to Int16 for OpenAI
          const int16Data = this.float32ToInt16(inputData);
          this.onDataCallback({
            mono: inputData,
            int16: int16Data
          });
        }
      };

      console.log('[WavRecorder] Microphone initialized');
      return true;
    } catch (error) {
      console.error('[WavRecorder] Failed to initialize:', error);
      throw error;
    }
  }

  /**
   * Start recording and call callback with audio data
   */
  async record(callback) {
    if (!this.source || !this.processor) {
      throw new Error('WavRecorder not initialized. Call begin() first.');
    }

    this.onDataCallback = callback;
    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
    this.recording = true;

    console.log('[WavRecorder] Recording started');
  }

  /**
   * Pause recording
   */
  pause() {
    if (this.recording) {
      this.source.disconnect(this.processor);
      this.recording = false;
      console.log('[WavRecorder] Recording paused');
    }
  }

  /**
   * Resume recording
   */
  resume() {
    if (!this.recording && this.source && this.processor) {
      this.source.connect(this.processor);
      this.recording = true;
      console.log('[WavRecorder] Recording resumed');
    }
  }

  /**
   * Stop recording and release resources
   */
  async end() {
    this.recording = false;

    if (this.processor) {
      this.processor.disconnect();
    }
    if (this.source) {
      this.source.disconnect();
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
    }
    if (this.audioContext) {
      await this.audioContext.close();
    }

    this.stream = null;
    this.audioContext = null;
    this.source = null;
    this.processor = null;
    this.onDataCallback = null;

    console.log('[WavRecorder] Recording ended');
  }

  /**
   * Convert Float32Array to Int16Array for OpenAI
   */
  float32ToInt16(float32Array) {
    const int16Array = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16Array;
  }

  /**
   * Convert Int16Array to base64 for WebSocket transmission
   */
  static int16ToBase64(int16Array) {
    const uint8Array = new Uint8Array(int16Array.buffer);
    let binary = '';
    for (let i = 0; i < uint8Array.length; i++) {
      binary += String.fromCharCode(uint8Array[i]);
    }
    return btoa(binary);
  }

  /**
   * Decode audio data to WAV file (for saving recordings)
   */
  static async decode(audioData, inputSampleRate, outputSampleRate) {
    const numChannels = 1;
    const bytesPerSample = 2; // 16-bit
    const dataLength = audioData.length * bytesPerSample;

    const buffer = new ArrayBuffer(44 + dataLength);
    const view = new DataView(buffer);

    // WAV header
    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true); // Subchunk1Size
    view.setUint16(20, 1, true); // AudioFormat (PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, outputSampleRate, true);
    view.setUint32(28, outputSampleRate * numChannels * bytesPerSample, true);
    view.setUint16(32, numChannels * bytesPerSample, true);
    view.setUint16(34, bytesPerSample * 8, true);
    writeString(36, 'data');
    view.setUint32(40, dataLength, true);

    // Write audio data
    const int16View = new Int16Array(buffer, 44);
    for (let i = 0; i < audioData.length; i++) {
      int16View[i] = audioData[i];
    }

    return new Blob([buffer], { type: 'audio/wav' });
  }
}


/**
 * WavStreamPlayer - Plays PCM16 audio from streaming source
 */
export class WavStreamPlayer {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 24000;
    this.audioContext = null;
    this.gainNode = null;
    this.scheduledBuffers = new Map();
    this.nextPlayTime = 0;
    this.isPlaying = false;
    this.currentTrackId = null;
  }

  /**
   * Initialize audio output context
   */
  async connect() {
    this.audioContext = new AudioContext({ sampleRate: this.sampleRate });
    this.gainNode = this.audioContext.createGain();
    this.gainNode.connect(this.audioContext.destination);
    this.nextPlayTime = this.audioContext.currentTime;

    console.log('[WavStreamPlayer] Audio output connected');
    return true;
  }

  /**
   * Add PCM16 audio data to playback queue
   * @param {string} base64Audio - Base64 encoded PCM16 audio
   * @param {string} trackId - Unique ID for this audio track
   */
  add16BitPCM(base64Audio, trackId) {
    if (!this.audioContext) {
      console.warn('[WavStreamPlayer] Not connected');
      return;
    }

    // Decode base64 to Int16Array
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const int16Array = new Int16Array(bytes.buffer);

    // Convert Int16 to Float32 for Web Audio API
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768.0;
    }

    // Create audio buffer
    const audioBuffer = this.audioContext.createBuffer(
      1, // mono
      float32Array.length,
      this.sampleRate
    );
    audioBuffer.getChannelData(0).set(float32Array);

    // Schedule playback
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.gainNode);

    // Schedule at next available time
    const startTime = Math.max(this.nextPlayTime, this.audioContext.currentTime);
    source.start(startTime);

    // Track for interruption
    this.currentTrackId = trackId;
    if (!this.scheduledBuffers.has(trackId)) {
      this.scheduledBuffers.set(trackId, []);
    }
    this.scheduledBuffers.get(trackId).push({
      source,
      startTime,
      duration: audioBuffer.duration
    });

    // Update next play time
    this.nextPlayTime = startTime + audioBuffer.duration;
    this.isPlaying = true;

    // Clean up when done
    source.onended = () => {
      const buffers = this.scheduledBuffers.get(trackId);
      if (buffers) {
        const idx = buffers.findIndex(b => b.source === source);
        if (idx !== -1) buffers.splice(idx, 1);
        if (buffers.length === 0) {
          this.scheduledBuffers.delete(trackId);
        }
      }
    };
  }

  /**
   * Interrupt current playback
   * @returns {Object} Track ID and sample offset for cancellation
   */
  async interrupt() {
    if (!this.audioContext || !this.currentTrackId) {
      return null;
    }

    const trackId = this.currentTrackId;
    const currentTime = this.audioContext.currentTime;

    // Calculate sample offset
    const buffers = this.scheduledBuffers.get(trackId);
    let sampleOffset = 0;

    if (buffers) {
      for (const buffer of buffers) {
        if (currentTime >= buffer.startTime &&
            currentTime < buffer.startTime + buffer.duration) {
          // Currently playing this buffer
          const timeIntoBuffer = currentTime - buffer.startTime;
          sampleOffset += Math.floor(timeIntoBuffer * this.sampleRate);
          break;
        } else if (currentTime >= buffer.startTime + buffer.duration) {
          // This buffer already played
          sampleOffset += Math.floor(buffer.duration * this.sampleRate);
        }

        // Stop the source
        try {
          buffer.source.stop();
        } catch (e) {
          // Already stopped
        }
      }

      this.scheduledBuffers.delete(trackId);
    }

    // Reset play time
    this.nextPlayTime = this.audioContext.currentTime;
    this.isPlaying = false;

    console.log(`[WavStreamPlayer] Interrupted at track ${trackId}, offset ${sampleOffset}`);

    return {
      trackId,
      offset: sampleOffset
    };
  }

  /**
   * Set playback volume
   * @param {number} volume - 0.0 to 1.0
   */
  setVolume(volume) {
    if (this.gainNode) {
      this.gainNode.gain.value = Math.max(0, Math.min(1, volume));
    }
  }

  /**
   * Disconnect and release resources
   */
  async disconnect() {
    // Stop all scheduled audio
    for (const [trackId, buffers] of this.scheduledBuffers) {
      for (const buffer of buffers) {
        try {
          buffer.source.stop();
        } catch (e) {}
      }
    }
    this.scheduledBuffers.clear();

    if (this.audioContext) {
      await this.audioContext.close();
    }

    this.audioContext = null;
    this.gainNode = null;
    this.nextPlayTime = 0;
    this.isPlaying = false;
    this.currentTrackId = null;

    console.log('[WavStreamPlayer] Disconnected');
  }
}


/**
 * RealtimeClient - WebSocket client for OpenAI Realtime API
 */
export class RealtimeClient {
  constructor(options = {}) {
    this.url = options.url;
    this.ws = null;
    this.isConnected = false;
    this.eventHandlers = new Map();
    this.messageQueue = [];
    this.sessionConfig = {};
  }

  /**
   * Connect to relay server
   */
  async connect() {
    return new Promise((resolve, reject) => {
      if (!this.url) {
        reject(new Error('WebSocket URL is required'));
        return;
      }

      console.log(`[RealtimeClient] Connecting to ${this.url}...`);

      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[RealtimeClient] Connected');
        this.isConnected = true;

        // Process queued messages
        while (this.messageQueue.length > 0) {
          const msg = this.messageQueue.shift();
          this.ws.send(JSON.stringify(msg));
        }

        resolve();
      };

      this.ws.onclose = (event) => {
        console.log(`[RealtimeClient] Disconnected: ${event.code}`);
        this.isConnected = false;
        this.emit('disconnected', { code: event.code, reason: event.reason });
      };

      this.ws.onerror = (error) => {
        console.error('[RealtimeClient] Error:', error);
        this.emit('error', error);
        reject(error);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleServerEvent(data);
        } catch (e) {
          console.error('[RealtimeClient] Failed to parse message:', e);
        }
      };
    });
  }

  /**
   * Handle incoming server events
   */
  handleServerEvent(event) {
    const eventType = event.type;

    // Log non-audio events (audio events are too verbose)
    if (!eventType.includes('audio')) {
      console.log(`[RealtimeClient] Received: ${eventType}`);
    }

    // Emit to specific handlers
    this.emit(eventType, event);

    // Emit to wildcard handlers
    this.emit('server.*', event);

    // Special handling for conversation updates
    if (eventType === 'response.audio.delta') {
      this.emit('conversation.updated', {
        item: { id: event.item_id },
        delta: { audio: event.delta }
      });
    }

    // Handle interruption
    if (eventType === 'input_audio_buffer.speech_started') {
      this.emit('conversation.interrupted', event);
    }
  }

  /**
   * Register event handler
   */
  on(eventType, handler) {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType).push(handler);
  }

  /**
   * Remove event handler
   */
  off(eventType, handler) {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const idx = handlers.indexOf(handler);
      if (idx !== -1) handlers.splice(idx, 1);
    }
  }

  /**
   * Emit event to handlers
   */
  emit(eventType, data) {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (e) {
          console.error(`[RealtimeClient] Handler error for ${eventType}:`, e);
        }
      });
    }
  }

  /**
   * Send event to server
   */
  send(eventType, payload = {}) {
    const event = { type: eventType, ...payload };

    if (this.isConnected && this.ws) {
      this.ws.send(JSON.stringify(event));
    } else {
      console.log('[RealtimeClient] Queuing message (not connected)');
      this.messageQueue.push(event);
    }
  }

  /**
   * Update session configuration
   */
  updateSession(config) {
    this.sessionConfig = { ...this.sessionConfig, ...config };
    this.send('session.update', { session: config });
  }

  /**
   * Append audio to input buffer
   * @param {Float32Array} audioData - Audio samples
   */
  appendInputAudio(audioData) {
    // Convert to Int16
    const int16Array = new Int16Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      const s = Math.max(-1, Math.min(1, audioData[i]));
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // Convert to base64
    const base64 = WavRecorder.int16ToBase64(int16Array);

    this.send('input_audio_buffer.append', { audio: base64 });
  }

  /**
   * Send text message
   */
  sendUserMessageContent(content) {
    this.send('conversation.item.create', {
      item: {
        type: 'message',
        role: 'user',
        content: content
      }
    });
    this.send('response.create');
  }

  /**
   * Cancel in-flight response
   */
  async cancelResponse(trackId, sampleOffset) {
    this.send('response.cancel');
    console.log(`[RealtimeClient] Cancelled response: ${trackId} at ${sampleOffset}`);
  }

  /**
   * Create a response (trigger assistant to respond)
   */
  createResponse() {
    this.send('response.create');
  }

  /**
   * Disconnect from server
   */
  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.isConnected = false;
    this.messageQueue = [];
  }

  /**
   * Reset client state
   */
  reset() {
    this.disconnect();
    this.eventHandlers.clear();
    this.sessionConfig = {};
  }
}

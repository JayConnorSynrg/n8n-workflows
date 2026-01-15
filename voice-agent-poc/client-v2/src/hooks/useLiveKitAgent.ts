import { useCallback, useRef, useState, useEffect } from 'react'
import { useStore } from '../lib/store'

// LiveKit client types (minimal inline definitions)
interface RoomOptions {
  adaptiveStream?: boolean
  dynacast?: boolean
  audioCaptureDefaults?: {
    echoCancellation?: boolean
    noiseSuppression?: boolean
    autoGainControl?: boolean
  }
}

interface DataReceivedCallback {
  payload: Uint8Array
  topic?: string
  participant?: unknown
}

interface UseLiveKitAgentOptions {
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: string) => void
}

// LiveKit connection states
type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

// Agent message types (sent via DataChannel)
interface AgentMessage {
  type: string
  [key: string]: unknown
}

export function useLiveKitAgent(options: UseLiveKitAgentOptions = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [error, setError] = useState<string | null>(null)

  const roomRef = useRef<any>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const volumeIntervalRef = useRef<number | null>(null)

  const {
    setSessionId,
    setAgentConnected,
    setAgentState,
    setInputVolume,
    setOutputVolume,
    addMessage,
    addToolCall,
    updateToolCall,
    reset
  } = useStore()

  // Start monitoring local microphone volume
  const startLocalVolumeMonitoring = useCallback(async () => {
    try {
      const audioContext = new AudioContext()
      audioContextRef.current = audioContext

      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8
      analyserRef.current = analyser

      // Get local microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      const source = audioContext.createMediaStreamSource(stream)
      source.connect(analyser)

      const dataArray = new Uint8Array(analyser.frequencyBinCount)

      volumeIntervalRef.current = window.setInterval(() => {
        analyser.getByteFrequencyData(dataArray)
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length
        const normalized = Math.min(1, average / 128)
        setInputVolume(normalized)
      }, 50)
    } catch (err) {
      console.error('Failed to start volume monitoring:', err)
    }
  }, [setInputVolume])

  // Stop volume monitoring
  const stopVolumeMonitoring = useCallback(() => {
    if (volumeIntervalRef.current) {
      clearInterval(volumeIntervalRef.current)
      volumeIntervalRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    analyserRef.current = null
  }, [])

  // Handle data messages from agent
  const handleDataMessage = useCallback((data: DataReceivedCallback) => {
    try {
      const decoder = new TextDecoder()
      const jsonStr = decoder.decode(data.payload)
      const message: AgentMessage = JSON.parse(jsonStr)

      switch (message.type) {
        case 'agent.state':
          setAgentState(message.state as 'listening' | 'thinking' | 'speaking' | null)
          break

        case 'agent.volume':
          setOutputVolume(message.volume as number)
          break

        case 'transcript.user':
          addMessage({
            role: 'user',
            content: message.text as string
          })
          break

        case 'transcript.assistant':
          addMessage({
            role: 'assistant',
            content: message.text as string
          })
          break

        case 'tool.call':
          addToolCall({
            id: message.call_id as string,
            name: message.name as string,
            status: 'pending',
            arguments: message.arguments as Record<string, unknown>
          })
          break

        case 'tool.executing':
          updateToolCall(message.call_id as string, { status: 'executing' })
          break

        case 'tool.completed':
          updateToolCall(message.call_id as string, {
            status: 'completed',
            result: message.result
          })
          break

        case 'tool.error':
          updateToolCall(message.call_id as string, {
            status: 'error',
            result: message.error
          })
          break

        case 'error':
          setError(message.message as string)
          options.onError?.(message.message as string)
          break

        default:
          console.log('Unknown message type:', message.type)
      }
    } catch (err) {
      console.error('Failed to parse data message:', err)
    }
  }, [setAgentState, setOutputVolume, addMessage, addToolCall, updateToolCall, options])

  // Connect to LiveKit room
  const connect = useCallback(
    async (livekitUrl: string, token: string) => {
      if (roomRef.current?.state === 'connected') {
        return
      }

      setConnectionState('connecting')
      setError(null)

      try {
        // Dynamically import LiveKit SDK
        const { Room, RoomEvent, ConnectionState } = await import('livekit-client')

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
          audioCaptureDefaults: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        } as RoomOptions)

        roomRef.current = room

        // Set up event handlers
        room.on(RoomEvent.Connected, () => {
          setConnectionState('connected')
          setSessionId(room.name || null)
          startLocalVolumeMonitoring()
          options.onConnect?.()
        })

        room.on(RoomEvent.Disconnected, () => {
          setConnectionState('disconnected')
          stopVolumeMonitoring()
          options.onDisconnect?.()
        })

        room.on(RoomEvent.Reconnecting, () => {
          setConnectionState('reconnecting')
        })

        room.on(RoomEvent.Reconnected, () => {
          setConnectionState('connected')
        })

        room.on(RoomEvent.DataReceived, handleDataMessage)

        // Helper to detect if participant is the voice agent
        const isVoiceAgent = (participant: any): boolean => {
          // Check various ways an agent can be identified:
          // 1. isAgent flag from LiveKit
          // 2. kind === 'agent' in metadata
          // 3. identity matches our agent name
          // 4. identity contains 'synrg' (our naming convention)
          const identity = participant.identity?.toLowerCase() || ''
          const kind = participant.kind || participant.metadata?.kind
          return (
            participant.isAgent === true ||
            kind === 'agent' ||
            identity === 'synrg-voice-agent' ||
            identity.includes('synrg') ||
            identity.includes('agent')
          )
        }

        room.on(RoomEvent.ParticipantConnected, (participant: any) => {
          console.log('Participant connected:', participant.identity, {
            isAgent: participant.isAgent,
            kind: participant.kind,
            metadata: participant.metadata
          })
          if (isVoiceAgent(participant)) {
            console.log('Voice agent connected!')
            setAgentConnected(true)
          }
        })

        room.on(RoomEvent.ParticipantDisconnected, (participant: any) => {
          console.log('Participant disconnected:', participant.identity)
          if (isVoiceAgent(participant)) {
            console.log('Voice agent disconnected!')
            setAgentConnected(false)
          }
        })

        // Reuse single AudioContext for output volume monitoring
        let outputAudioContext: AudioContext | null = null
        let outputAnalyser: AnalyserNode | null = null

        // Monitor remote audio (agent speaking) - ATTACH FOR PLAYBACK
        room.on(RoomEvent.TrackSubscribed, (track: any, _pub: any, participant: any) => {
          if (track.kind === 'audio') {
            console.log('Audio track subscribed from:', participant.identity, 'track:', track.sid)

            // Attach audio track to play through speakers
            const audioElement = track.attach() as HTMLAudioElement
            audioElement.id = `audio-${participant.identity}-${track.sid}`

            // Configure for playback
            audioElement.autoplay = true
            audioElement.playsInline = true
            audioElement.muted = false
            audioElement.volume = 1.0

            // Add to DOM (hidden but functional)
            audioElement.style.display = 'none'
            document.body.appendChild(audioElement)

            // Handle autoplay blocking - browsers require user interaction
            const playAudio = async () => {
              try {
                await audioElement.play()
                console.log('Audio playback started for track:', track.sid)
              } catch (err) {
                console.warn('Autoplay blocked, waiting for user interaction:', err)
                // Add one-time click handler to resume audio
                const resumeAudio = async () => {
                  try {
                    await audioElement.play()
                    console.log('Audio resumed after user interaction')
                  } catch (e) {
                    console.error('Failed to resume audio:', e)
                  }
                  document.removeEventListener('click', resumeAudio)
                  document.removeEventListener('touchstart', resumeAudio)
                }
                document.addEventListener('click', resumeAudio, { once: true })
                document.addEventListener('touchstart', resumeAudio, { once: true })
              }
            }
            playAudio()

            // Monitor output volume from agent audio track
            if (isVoiceAgent(participant)) {
              try {
                // Create or reuse AudioContext
                if (!outputAudioContext || outputAudioContext.state === 'closed') {
                  outputAudioContext = new AudioContext()
                }

                // Resume context if suspended (autoplay policy)
                if (outputAudioContext.state === 'suspended') {
                  outputAudioContext.resume()
                }

                const source = outputAudioContext.createMediaStreamSource(
                  new MediaStream([track.mediaStreamTrack])
                )
                outputAnalyser = outputAudioContext.createAnalyser()
                outputAnalyser.fftSize = 256
                outputAnalyser.smoothingTimeConstant = 0.8
                source.connect(outputAnalyser)

                const dataArray = new Uint8Array(outputAnalyser.frequencyBinCount)
                const updateVolume = () => {
                  if (audioElement.parentElement && outputAnalyser) {
                    outputAnalyser.getByteFrequencyData(dataArray)
                    const average = dataArray.reduce((a, b) => a + b) / dataArray.length
                    const normalized = Math.min(1, average / 128)
                    setOutputVolume(normalized)
                    requestAnimationFrame(updateVolume)
                  }
                }
                updateVolume()
              } catch (err) {
                console.error('Failed to setup output volume monitoring:', err)
              }
            }
          }
        })

        // Clean up audio elements when tracks are unsubscribed
        room.on(RoomEvent.TrackUnsubscribed, (track: any, _pub: any, participant: any) => {
          if (track.kind === 'audio') {
            // Remove the audio element from DOM
            const audioElement = document.getElementById(`audio-${participant.identity}-${track.sid}`)
            if (audioElement) {
              audioElement.remove()
              console.log('Agent audio track detached:', track.sid)
            }
            // Also detach from the track
            track.detach()
          }
        })

        // Connect to the room
        await room.connect(livekitUrl, token, {
          autoSubscribe: true
        })

        console.log('Connected to LiveKit room:', room.name)

        // Check for existing participants (agent might already be in room)
        room.remoteParticipants.forEach((participant: any) => {
          console.log('Existing participant:', participant.identity, {
            isAgent: participant.isAgent,
            kind: participant.kind
          })
          if (isVoiceAgent(participant)) {
            console.log('Voice agent already in room!')
            setAgentConnected(true)

            // Subscribe to existing audio tracks
            participant.trackPublications.forEach((pub: any) => {
              if (pub.track && pub.track.kind === 'audio') {
                console.log('Existing audio track found:', pub.track.sid)
                // The TrackSubscribed event should fire for these
              }
            })
          }
        })

        // Enable microphone for voice input
        await room.localParticipant.setMicrophoneEnabled(true)
        console.log('Microphone enabled')

      } catch (err) {
        setConnectionState('disconnected')
        const message = err instanceof Error ? err.message : 'Connection failed'
        setError(message)
        options.onError?.(message)
      }
    },
    [setSessionId, setAgentConnected, setOutputVolume, startLocalVolumeMonitoring, stopVolumeMonitoring, handleDataMessage, options]
  )

  // Disconnect from LiveKit room
  const disconnect = useCallback(() => {
    if (roomRef.current) {
      roomRef.current.disconnect()
      roomRef.current = null
    }
    stopVolumeMonitoring()
    reset()
    setConnectionState('disconnected')
  }, [stopVolumeMonitoring, reset])

  // Send data message to agent
  const sendData = useCallback((data: Record<string, unknown>) => {
    if (roomRef.current?.state === 'connected') {
      const encoder = new TextEncoder()
      const payload = encoder.encode(JSON.stringify(data))
      roomRef.current.localParticipant.publishData(payload, {
        reliable: true
      })
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    connect,
    disconnect,
    sendData,
    isConnected: connectionState === 'connected',
    isConnecting: connectionState === 'connecting',
    isReconnecting: connectionState === 'reconnecting',
    connectionState,
    error
  }
}

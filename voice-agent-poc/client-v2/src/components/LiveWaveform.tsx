import { useRef, useEffect, useState, useCallback } from 'react'

interface LiveWaveformProps {
  active?: boolean
  volume?: number // Use external volume instead of capturing audio
  barWidth?: number
  barGap?: number
  barColor?: string
  height?: number
  sensitivity?: number
  fadeEdges?: boolean
  className?: string
}

/**
 * LiveWaveform - Visualizes audio input as animated bars
 *
 * IMPORTANT: This component uses external volume data (from useLiveKitAgent)
 * instead of capturing audio directly. This prevents conflicts with:
 * - LiveKit's audio capture
 * - Recall.ai's meeting audio injection
 * - Other components using getUserMedia
 */
export function LiveWaveform({
  active = false,
  volume = 0,
  barWidth = 3,
  barGap = 2,
  barColor = 'rgba(139, 92, 246, 0.6)',
  height = 64,
  sensitivity = 1.2,
  fadeEdges = true,
  className = ''
}: LiveWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animationRef = useRef<number | null>(null)
  const volumeHistoryRef = useRef<number[]>([])

  const [dimensions, setDimensions] = useState({ width: 0, height })

  // Calculate number of bars based on container width
  const numBars = Math.floor(dimensions.width / (barWidth + barGap))

  // FIX: Safe color helper — avoids fragile regex alpha replacement
  const getBarColor = (baseColor: string, alpha: number): string => {
    try {
      const rgbaMatch = baseColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
      if (rgbaMatch) {
        return `rgba(${rgbaMatch[1]}, ${rgbaMatch[2]}, ${rgbaMatch[3]}, ${alpha})`
      }
    } catch {}
    // Fallback: default brand purple
    return `rgba(139, 92, 246, ${alpha})`
  }

  // Draw waveform using volume history
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // FIX: roundRect browser compatibility polyfill
    if (!CanvasRenderingContext2D.prototype.roundRect) {
      CanvasRenderingContext2D.prototype.roundRect = function(
        x: number, y: number, w: number, h: number, r: number
      ) {
        if (w < 2 * r) r = w / 2
        if (h < 2 * r) r = h / 2
        this.beginPath()
        this.moveTo(x + r, y)
        this.arcTo(x + w, y, x + w, y + h, r)
        this.arcTo(x + w, y + h, x, y + h, r)
        this.arcTo(x, y + h, x, y, r)
        this.arcTo(x, y, x + w, y, r)
        this.closePath()
        return this
      }
    }

    // Update volume history (shift left, add new value)
    const history = volumeHistoryRef.current
    if (history.length >= numBars) {
      history.shift()
    }
    // Add some variation to make it look more natural
    const variation = (Math.random() - 0.5) * 0.2 * volume
    history.push(Math.max(0, Math.min(1, volume + variation)))

    // Pad history if not enough values
    while (history.length < numBars) {
      history.unshift(0)
    }

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Scale for retina
    const dpr = window.devicePixelRatio || 1

    // Calculate bar positions
    const totalBarWidth = barWidth + barGap
    const startX = (canvas.width / dpr - numBars * totalBarWidth + barGap) / 2

    // Draw bars from history
    for (let i = 0; i < numBars; i++) {
      const value = history[i] || 0

      // Calculate bar height with sensitivity
      const barHeight = Math.max(
        4,
        value * (canvas.height / dpr - 8) * sensitivity
      )

      // Calculate x position
      const x = startX + i * totalBarWidth

      // Fade edges
      let alpha = 1
      if (fadeEdges) {
        const edgeRatio = Math.min(i, numBars - 1 - i) / (numBars * 0.15)
        alpha = Math.min(1, edgeRatio)
      }

      // FIX: Use safe getBarColor helper instead of fragile regex
      ctx.fillStyle = getBarColor(barColor, alpha);

      // Center vertically
      const y = (canvas.height / dpr - barHeight) / 2

      // Draw rounded bar
      const radius = barWidth / 2
      ctx.beginPath()
      ctx.roundRect(x * dpr, y * dpr, barWidth * dpr, barHeight * dpr, radius * dpr)
      ctx.fill()
    }

    animationRef.current = requestAnimationFrame(draw)
  }, [numBars, barWidth, barGap, barColor, sensitivity, fadeEdges, volume])

  // Handle resize
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateDimensions = () => {
      const rect = container.getBoundingClientRect()
      setDimensions({ width: rect.width, height })
    }

    updateDimensions()

    const resizeObserver = new ResizeObserver(updateDimensions)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [height])

  // Set canvas size for retina
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || dimensions.width === 0) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = dimensions.width * dpr
    canvas.height = dimensions.height * dpr
    canvas.style.width = `${dimensions.width}px`
    canvas.style.height = `${dimensions.height}px`
  }, [dimensions])

  // Start/stop animation based on active prop
  useEffect(() => {
    if (active && dimensions.width > 0) {
      // FIX: Cancel any existing animation (active or idle) before starting active loop
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
        animationRef.current = null
      }
      // Clear history when becoming active
      volumeHistoryRef.current = []
      draw()
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
        animationRef.current = null
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
        animationRef.current = null
      }
    }
  }, [active, draw, dimensions.width])

  // Idle animation when not active
  useEffect(() => {
    if (active) return

    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // FIX: Cancel any existing RAF (active or previous idle) before starting idle loop
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current)
      animationRef.current = null
    }

    let time = 0

    const drawIdle = () => {
      const dpr = window.devicePixelRatio || 1
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      const totalBarWidth = barWidth + barGap
      const startX = (canvas.width / dpr - numBars * totalBarWidth + barGap) / 2

      for (let i = 0; i < numBars; i++) {
        // Gentle wave animation
        const wave = Math.sin(time * 2 + i * 0.3) * 0.3 + 0.5
        const barHeight = 4 + wave * 8

        const x = startX + i * totalBarWidth
        const y = (canvas.height / dpr - barHeight) / 2

        // Fade edges
        let alpha = 0.3
        if (fadeEdges) {
          const edgeRatio = Math.min(i, numBars - 1 - i) / (numBars * 0.15)
          alpha = Math.min(0.3, edgeRatio * 0.3)
        }

        // FIX: Use safe getBarColor helper instead of fragile regex
        ctx.fillStyle = getBarColor(barColor, alpha)

        const radius = barWidth / 2
        ctx.beginPath()
        ctx.roundRect(x * dpr, y * dpr, barWidth * dpr, barHeight * dpr, radius * dpr)
        ctx.fill()
      }

      time += 0.016
      // FIX: Store idle RAF in shared animationRef (not a local variable)
      animationRef.current = requestAnimationFrame(drawIdle)
    }

    drawIdle()
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
        animationRef.current = null
      }
    }
  }, [active, numBars, barWidth, barGap, barColor, fadeEdges, dimensions])

  return (
    <div
      ref={containerRef}
      className={`relative ${className}`}
      style={{ height }}
    >
      <canvas
        ref={canvasRef}
        className="w-full h-full"
      />
    </div>
  )
}

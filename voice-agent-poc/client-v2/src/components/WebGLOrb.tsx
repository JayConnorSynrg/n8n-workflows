import { useEffect, useRef, useState, useMemo } from 'react'
import { motion } from 'framer-motion'

type AgentState = 'listening' | 'thinking' | 'speaking' | null

interface WebGLOrbProps {
  agentState: AgentState
  inputVolume?: number
  outputVolume?: number
  isConnected?: boolean
  size?: number
}

/**
 * Animated Orb Component with Outer Ring
 * - Inner orb: Original WebGL shader (constant, slow animation)
 * - Outer ring: Smooth gradient ring with audio-reactive glow
 */
export function WebGLOrb({
  agentState,
  inputVolume = 0,
  outputVolume = 0,
  isConnected = false,
  size = 280
}: WebGLOrbProps) {
  const canvasContainerRef = useRef<HTMLDivElement>(null)
  const [useWebGL, setUseWebGL] = useState(true)
  const animationRef = useRef<number | null>(null)
  const programRef = useRef<any>(null)

  // Smoothed volume for outer ring (eased transitions)
  const [smoothedVolume, setSmoothedVolume] = useState(0)

  // Gap between inner orb and outer ring (controls ring width)
  const ringGap = 18
  // Inner orb size (smaller than container to leave room for ring)
  const innerSize = size - ringGap * 2

  // Smooth volume changes with easing
  useEffect(() => {
    const targetVolume = Math.max(inputVolume, outputVolume)
    const interval = setInterval(() => {
      setSmoothedVolume(prev => {
        const diff = targetVolume - prev
        if (Math.abs(diff) < 0.005) return targetVolume
        return prev + diff * 0.08 // Smooth easing
      })
    }, 16) // ~60fps
    return () => clearInterval(interval)
  }, [inputVolume, outputVolume])

  // Outer ring color based on state
  const ringColor = useMemo(() => {
    if (!isConnected) return { r: 139, g: 92, b: 246 } // Purple
    if (agentState === 'speaking') return { r: 78, g: 234, b: 170 } // Mint #4EEAAA
    if (agentState === 'listening') return { r: 34, g: 211, b: 238 } // Cyan #22D3EE
    if (agentState === 'thinking') return { r: 139, g: 92, b: 246 } // Purple #8B5CF6
    return { r: 78, g: 234, b: 170 } // Mint - ready
  }, [isConnected, agentState])

  // WebGL initialization for inner orb
  useEffect(() => {
    const container = canvasContainerRef.current
    if (!container || !useWebGL) return

    let cleanup: (() => void) | null = null

    const initWebGL = async () => {
      try {
        const { Mesh, Program, Renderer, Triangle, Vec3 } = await import('ogl')

        const renderer = new Renderer({ alpha: true, premultipliedAlpha: false })
        const gl = renderer.gl

        if (!gl) {
          setUseWebGL(false)
          return
        }

        gl.clearColor(0, 0, 0, 0)
        container.appendChild(gl.canvas)

        const vert = /* glsl */ `
          precision highp float;
          attribute vec2 position;
          attribute vec2 uv;
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = vec4(position, 0.0, 1.0);
          }
        `

        // Original orb shader - simple, elegant
        const frag = /* glsl */ `
          precision highp float;

          uniform float iTime;
          uniform vec3 iResolution;
          uniform vec3 backgroundColor;
          varying vec2 vUv;

          vec3 hash33(vec3 p3) {
            p3 = fract(p3 * vec3(0.1031, 0.11369, 0.13787));
            p3 += dot(p3, p3.yxz + 19.19);
            return -1.0 + 2.0 * fract(vec3(p3.x + p3.y, p3.x + p3.z, p3.y + p3.z) * p3.zyx);
          }

          float snoise3(vec3 p) {
            const float K1 = 0.333333333;
            const float K2 = 0.166666667;
            vec3 i = floor(p + (p.x + p.y + p.z) * K1);
            vec3 d0 = p - (i - (i.x + i.y + i.z) * K2);
            vec3 e = step(vec3(0.0), d0 - d0.yzx);
            vec3 i1 = e * (1.0 - e.zxy);
            vec3 i2 = 1.0 - e.zxy * (1.0 - e);
            vec3 d1 = d0 - (i1 - K2);
            vec3 d2 = d0 - (i2 - K1);
            vec3 d3 = d0 - 0.5;
            vec4 h = max(0.6 - vec4(dot(d0,d0), dot(d1,d1), dot(d2,d2), dot(d3,d3)), 0.0);
            vec4 n = h * h * h * h * vec4(dot(d0,hash33(i)), dot(d1,hash33(i+i1)), dot(d2,hash33(i+i2)), dot(d3,hash33(i+1.0)));
            return dot(vec4(31.316), n);
          }

          vec4 extractAlpha(vec3 colorIn) {
            float a = max(max(colorIn.r, colorIn.g), colorIn.b);
            return vec4(colorIn.rgb / (a + 1e-5), a);
          }

          // SYNRG Brand Colors
          const vec3 baseColor1 = vec3(0.545, 0.361, 0.965);  // Purple #8B5CF6
          const vec3 baseColor2 = vec3(0.306, 0.918, 0.667);  // Mint #4EEAAA
          const vec3 baseColor3 = vec3(0.4, 0.25, 0.75);      // Deep purple
          const float innerRadius = 0.6;
          const float noiseScale = 0.65;

          float light1(float intensity, float attenuation, float dist) {
            return intensity / (1.0 + dist * attenuation);
          }
          float light2(float intensity, float attenuation, float dist) {
            return intensity / (1.0 + dist * dist * attenuation);
          }

          vec4 draw(vec2 uv) {
            float ang = atan(uv.y, uv.x);
            float len = length(uv);
            float invLen = len > 0.0 ? 1.0 / len : 0.0;
            float bgLuminance = dot(backgroundColor, vec3(0.299, 0.587, 0.114));

            // Gentle constant animation (slightly faster)
            float animTime = iTime * 0.5;

            float n0 = snoise3(vec3(uv * noiseScale, animTime * 0.5)) * 0.5 + 0.5;
            float r0 = mix(mix(innerRadius, 1.0, 0.4), mix(innerRadius, 1.0, 0.6), n0);
            float d0 = distance(uv, (r0 * invLen) * uv);
            float v0 = light1(1.0, 10.0, d0);

            v0 *= smoothstep(r0 * 1.05, r0, len);
            float innerFade = smoothstep(r0 * 0.8, r0 * 0.95, len);
            v0 *= mix(innerFade, 1.0, bgLuminance * 0.7);
            float cl = cos(ang + animTime * 2.0) * 0.5 + 0.5;

            float a = animTime * -1.0;
            vec2 pos = vec2(cos(a), sin(a)) * r0;
            float d = distance(uv, pos);
            float v1 = light2(1.5, 5.0, d);
            v1 *= light1(1.0, 50.0, d0);

            float v2 = smoothstep(1.0, mix(innerRadius, 1.0, n0 * 0.5), len);
            float v3 = smoothstep(innerRadius, mix(innerRadius, 1.0, 0.5), len);

            vec3 colBase = mix(baseColor1, baseColor2, cl);
            float fadeAmount = mix(1.0, 0.1, bgLuminance);

            vec3 darkCol = mix(baseColor3, colBase, v0);
            darkCol = (darkCol + v1) * v2 * v3;
            darkCol = clamp(darkCol, 0.0, 1.0);

            vec3 lightCol = (colBase + v1) * mix(1.0, v2 * v3, fadeAmount);
            lightCol = mix(backgroundColor, lightCol, v0);
            lightCol = clamp(lightCol, 0.0, 1.0);

            return extractAlpha(mix(darkCol, lightCol, bgLuminance));
          }

          void main() {
            vec2 center = iResolution.xy * 0.5;
            float sz = min(iResolution.x, iResolution.y);
            vec2 uv = (vUv * iResolution.xy - center) / sz * 2.0;
            vec4 col = draw(uv);
            gl_FragColor = vec4(col.rgb * col.a, col.a);
          }
        `

        const geometry = new Triangle(gl)
        const program = new Program(gl, {
          vertex: vert,
          fragment: frag,
          uniforms: {
            iTime: { value: 0 },
            iResolution: { value: new Vec3(innerSize, innerSize, 1) },
            backgroundColor: { value: new Vec3(1, 1, 1) }
          }
        })
        programRef.current = program

        const mesh = new Mesh(gl, { geometry, program })

        const dpr = window.devicePixelRatio || 1
        renderer.setSize(innerSize * dpr, innerSize * dpr)
        gl.canvas.style.width = innerSize + 'px'
        gl.canvas.style.height = innerSize + 'px'
        program.uniforms.iResolution.value.set(innerSize * dpr, innerSize * dpr, 1)

        // Animation loop - constant slow speed
        const update = (t: number) => {
          animationRef.current = requestAnimationFrame(update)
          program.uniforms.iTime.value = t * 0.001
          renderer.render({ scene: mesh })
        }
        animationRef.current = requestAnimationFrame(update)

        cleanup = () => {
          if (animationRef.current) cancelAnimationFrame(animationRef.current)
          if (container.contains(gl.canvas)) container.removeChild(gl.canvas)
          try { gl.getExtension('WEBGL_lose_context')?.loseContext() } catch (e) {}
        }
      } catch (error) {
        console.warn('WebGL initialization failed:', error)
        setUseWebGL(false)
      }
    }

    initWebGL()
    return () => { if (cleanup) cleanup() }
  }, [innerSize, useWebGL])

  // Inject CSS keyframes for outer ring rotation
  useEffect(() => {
    const styleId = 'webgl-orb-keyframes'
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style')
      style.id = styleId
      style.textContent = `
        @keyframes outerRingRotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `
      document.head.appendChild(style)
    }
  }, [])

  return (
    <div
      className="relative"
      style={{ width: size, height: size }}
    >
      {/* Outer ring - simple border with glow (like light attenuation) */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          top: 2,
          left: 2,
          right: 2,
          bottom: 2,
          border: `3px solid rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${0.6 + smoothedVolume * 0.4})`,
          boxShadow: `
            0 0 ${8 + smoothedVolume * 15}px rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${0.4 + smoothedVolume * 0.4}),
            0 0 ${15 + smoothedVolume * 25}px rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${0.2 + smoothedVolume * 0.3}),
            0 0 ${25 + smoothedVolume * 35}px rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${0.1 + smoothedVolume * 0.2}),
            inset 0 0 ${10 + smoothedVolume * 15}px rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${0.1 + smoothedVolume * 0.15})
          `,
        }}
        animate={{
          opacity: 0.7 + smoothedVolume * 0.3,
          scale: 1 + smoothedVolume * 0.02
        }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      />

      {/* Inner orb container - centered within outer ring */}
      <div
        ref={canvasContainerRef}
        className="absolute rounded-full overflow-hidden"
        style={{
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: innerSize,
          height: innerSize,
        }}
      />

      {/* Audio-reactive ripple gradient - subtle outward pulse */}
      {smoothedVolume > 0.05 && (
        <>
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background: `radial-gradient(circle at center,
                transparent 0%,
                transparent 45%,
                rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${smoothedVolume * 0.15}) 50%,
                rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${smoothedVolume * 0.08}) 60%,
                transparent 70%
              )`,
            }}
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{
              scale: 1.1 + smoothedVolume * 0.15,
              opacity: 0
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'easeOut'
            }}
          />
          <motion.div
            className="absolute inset-0 rounded-full pointer-events-none"
            style={{
              background: `radial-gradient(circle at center,
                transparent 0%,
                transparent 45%,
                rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${smoothedVolume * 0.12}) 50%,
                rgba(${ringColor.r}, ${ringColor.g}, ${ringColor.b}, ${smoothedVolume * 0.06}) 60%,
                transparent 70%
              )`,
            }}
            initial={{ scale: 1, opacity: 0.4 }}
            animate={{
              scale: 1.08 + smoothedVolume * 0.12,
              opacity: 0
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'easeOut',
              delay: 0.75
            }}
          />
        </>
      )}

      {/* CSS Fallback for inner orb */}
      {!useWebGL && (
        <div
          className="absolute rounded-full"
          style={{
            top: ringGap,
            left: ringGap,
            width: innerSize,
            height: innerSize,
            background: `radial-gradient(circle at 40% 40%,
              rgba(139, 92, 246, 0.9) 0%,
              rgba(78, 234, 170, 0.7) 40%,
              rgba(139, 92, 246, 0.5) 70%,
              transparent 100%)`,
          }}
        />
      )}
    </div>
  )
}

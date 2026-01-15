import { motion } from 'framer-motion'

interface StatusIndicatorProps {
  isConnected: boolean
  isConnecting: boolean
  agentConnected?: boolean
  error?: string | null
}

export function StatusIndicator({
  isConnected,
  isConnecting,
  agentConnected,
  error
}: StatusIndicatorProps) {
  const getStatus = () => {
    if (error) return { label: 'Error', color: 'bg-red-500', pulse: false }
    if (isConnecting) return { label: 'Connecting', color: 'bg-amber-500', pulse: true }
    if (isConnected && agentConnected) return { label: 'Agent Ready', color: 'bg-emerald-500', pulse: false }
    if (isConnected) return { label: 'Waiting for agent...', color: 'bg-blue-500', pulse: true }
    return { label: 'Disconnected', color: 'bg-gray-400', pulse: false }
  }

  const status = getStatus()

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <motion.div
          className={`w-2.5 h-2.5 rounded-full ${status.color}`}
          animate={status.pulse ? { scale: [1, 1.2, 1] } : {}}
          transition={status.pulse ? { duration: 1, repeat: Infinity } : {}}
        />
        {status.pulse && (
          <motion.div
            className={`absolute inset-0 w-2.5 h-2.5 rounded-full ${status.color}`}
            animate={{ scale: [1, 2], opacity: [0.5, 0] }}
            transition={{ duration: 1, repeat: Infinity }}
          />
        )}
      </div>
      <span className="text-xs font-medium text-gray-500">
        {status.label}
      </span>
    </div>
  )
}

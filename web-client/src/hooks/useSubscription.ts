import { useEffect, useRef, useState } from 'react'
import { SERVER_URL } from '@/utils/config'

const WS_URL = SERVER_URL.replace('http', 'ws')

export type ChangeEvent = {
    operation: 'insert' | 'update' | 'replace' | 'delete' | 'invalidate'
    documentKey: { _id: string }
    fullDocument?: Record<string, any>
    updateDescription?: {
        updatedFields: Record<string, any>
        removedFields: string[]
    }
}

export const useSubscription = (
    collectionName: string | undefined,
    onData: (event: ChangeEvent) => void
) => {
    const [isConnected, setIsConnected] = useState(false)
    const wsRef = useRef<WebSocket | null>(null)
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    useEffect(() => {
        if (!collectionName) return

        const connect = () => {
            // Close existing connection if any
            if (wsRef.current) {
                wsRef.current.close()
            }

            const url = `${WS_URL}/platform/api-builder/ws/subscribe/${collectionName}`
            const ws = new WebSocket(url)
            wsRef.current = ws

            ws.onopen = () => {
                setIsConnected(true)
                console.log(`Subscribed to ${collectionName}`)
            }

            ws.onmessage = (message) => {
                try {
                    const data = JSON.parse(message.data)
                    onData(data)
                } catch (err) {
                    console.error('Failed to parse WebSocket message', err)
                }
            }

            ws.onclose = () => {
                setIsConnected(false)
                console.log(`Disconnected from ${collectionName}, reconnecting in 3s...`)
                reconnectTimeoutRef.current = setTimeout(connect, 3000)
            }

            ws.onerror = (err) => {
                console.error('WebSocket error:', err)
                ws.close()
            }
        }

        connect()

        return () => {
            if (wsRef.current) {
                wsRef.current.onclose = null // Prevent auto-reconnect on cleanup
                wsRef.current.close()
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current)
            }
        }
    }, [collectionName]) // Re-subscribe if collectionName changes

    return { isConnected }
}

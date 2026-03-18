/**
 * Email-related types aligned with EmailService REST API.
 * Mirrors the dict shapes returned by EmailService methods.
 */

/** Email header returned by GET /api/email/inbox and search. */
export interface EmailHeader {
  uid: string
  subject: string
  from: string
  to: string
  date: string
  message_id: string
  is_read: boolean
}

/** Full email with body returned by GET /api/email/{uid}. */
export interface EmailDetail extends EmailHeader {
  cc: string
  body: string
  has_attachments: boolean
}

/** Payload for POST /api/email/search. */
export interface EmailSearchRequest {
  query: string
  folder?: string
  limit?: number
}

/** WebSocket event emitted when a new email arrives via IMAP IDLE. */
export interface WsEmailReceivedMessage {
  type: 'email.received'
  folder: string
}

/** WebSocket event emitted after a successful send. */
export interface WsEmailSentMessage {
  type: 'email.sent'
  message_id?: string
}

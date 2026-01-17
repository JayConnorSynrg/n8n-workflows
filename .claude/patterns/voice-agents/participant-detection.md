# Participant Detection & Audio Subscription Pattern

**Pattern ID**: `voice-agents/participant-detection`
**Category**: Voice Agent Architecture
**Severity**: HIGH
**Created**: 2026-01-17
**Source**: Voice Agent POC debugging session

---

## Overview

For LiveKit voice agents to receive audio from specific participants (like Recall.ai Output Media clients), explicit participant detection and audio subscription verification is required.

---

## The Problem

When a LiveKit agent starts:
1. It may start before the client connects
2. Auto-subscribe may not work for all participant types
3. The session may bind to the wrong participant
4. Audio tracks may not be published immediately

**Result**: Agent appears to work (greeting plays) but never responds to speech.

---

## Complete Detection Pattern

### Wait for Client with Audio Track

```python
async def wait_for_client_with_audio(
    ctx: JobContext,
    timeout_seconds: float = 300.0
) -> Optional[rtc.RemoteParticipant]:
    """Wait for Output Media client to connect AND publish audio.

    CRITICAL: Wait for audio track, not just participant connection.
    """
    start_time = asyncio.get_event_loop().time()
    check_interval = 0.5  # Fast polling

    client_participant = None

    while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
        for participant in ctx.room.remote_participants.values():
            if participant is None:
                continue

            identity = getattr(participant, 'identity', None)
            if identity is None:
                continue

            # Output Media client identity pattern
            if identity.lower().startswith('output-media-'):
                if client_participant is None:
                    logger.info(f"Client found: {participant.identity}")
                    client_participant = participant

                # Check for audio track
                for pub in participant.track_publications.values():
                    if pub.kind == rtc.TrackKind.KIND_AUDIO:
                        logger.info(f"Client audio track found: {pub.sid}")
                        return participant

        await asyncio.sleep(check_interval)

    if client_participant:
        logger.warning("Client connected but no audio track published")
        return client_participant

    logger.warning(f"Timeout waiting for client after {timeout_seconds}s")
    return None
```

### Verify Audio Subscription

```python
async def verify_audio_subscription(participant) -> bool:
    """Verify agent is subscribed to client's audio track."""
    audio_track_subscribed = False

    for pub in participant.track_publications.values():
        if pub.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"Audio track: {pub.sid}, subscribed: {pub.subscribed}")

            if pub.subscribed:
                audio_track_subscribed = True
                if pub.track:
                    logger.info("Audio track is subscribed and ready!")
                else:
                    logger.warning("Subscribed but track is None!")
            else:
                # Force subscription
                logger.warning("Audio track NOT subscribed! Forcing...")
                try:
                    pub.set_subscribed(True)
                    await asyncio.sleep(0.5)
                    if pub.subscribed:
                        logger.info("Manual subscription successful!")
                        audio_track_subscribed = True
                    else:
                        logger.error("Manual subscription FAILED!")
                except Exception as e:
                    logger.error(f"Subscription error: {e}")

    return audio_track_subscribed
```

---

## Session Start with Participant Identity

### Critical: Link Session to Specific Participant

```python
# After client detection
client_participant = await wait_for_client_with_audio(ctx)

if client_participant:
    # Allow Web Audio API initialization
    await asyncio.sleep(1.5)

    # Verify subscription
    await verify_audio_subscription(client_participant)

    participant_identity = client_participant.identity
else:
    participant_identity = None  # Will not receive audio

# Start session linked to client
await session.start(
    agent=agent,
    room=ctx.room,
    room_options=room_io.RoomOptions(
        # ...audio options...
        participant_identity=participant_identity,  # CRITICAL
    ),
)
```

---

## Participant Kinds Configuration

### Accept All Participant Types

Recall.ai Output Media may not be recognized as STANDARD participant:

```python
room_options=room_io.RoomOptions(
    # ...
    participant_kinds=[
        rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,
        rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
        rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
        rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
    ],
)
```

---

## Room Event Handlers for Debugging

### Track Lifecycle Events

```python
@ctx.room.on("track_subscribed")
def on_track_subscribed(track, publication, participant):
    if track.kind == rtc.TrackKind.KIND_AUDIO:
        logger.info(f"AUDIO TRACK SUBSCRIBED:")
        logger.info(f"  Track SID: {track.sid}")
        logger.info(f"  Source: {publication.source}")
        logger.info(f"  Participant: {participant.identity}")

@ctx.room.on("track_published")
def on_track_published(publication, participant):
    logger.info(f"TRACK PUBLISHED by {participant.identity}:")
    logger.info(f"  Kind: {publication.kind}")
    logger.info(f"  Source: {publication.source}")

@ctx.room.on("participant_connected")
def on_participant_connected(participant):
    logger.info(f"PARTICIPANT CONNECTED: {participant.identity}")
    for pub in participant.track_publications.values():
        logger.info(f"  Has track: {pub.kind} / {pub.source}")
```

---

## Identity Patterns

### Output Media Client

```
Pattern: output-media-{session_id}
Example: output-media-abc123xyz
```

### Agent

```
Pattern: synrg-voice-agent or agent-{session_id}
Example: synrg-voice-agent
```

### Detection Logic

```python
def is_output_media_client(participant) -> bool:
    identity = getattr(participant, 'identity', '')
    return identity.lower().startswith('output-media-')

def is_agent(participant) -> bool:
    identity = getattr(participant, 'identity', '').lower()
    return 'agent' in identity or identity.startswith('synrg')
```

---

## Connection Flow Timeline

```
1. Agent starts, connects to room
2. Agent waits for client (up to 5 min)
3. Output Media webpage loads
4. Client gets token, connects to room
5. Client publishes audio track (from getUserMedia)
6. Agent detects client + audio track
7. Agent verifies subscription
8. Agent starts session linked to client
9. Agent sends greeting
10. Audio pipeline active: Client speech → VAD → STT → LLM → TTS → Audio out
```

---

## Failure Modes

### 1. Agent Starts Before Client

**Symptom**: Greeting plays, no responses

**Cause**: Session not linked to client

**Fix**: Wait for client before `session.start()`

### 2. Auto-Subscribe Fails

**Symptom**: Client connected, no audio frames

**Cause**: Track subscription didn't happen

**Fix**: Manual `pub.set_subscribed(True)`

### 3. Wrong Participant Type

**Symptom**: Client detected but filtered out

**Cause**: `participant_kinds` too restrictive

**Fix**: Include all participant kinds

### 4. Audio Track Published Late

**Symptom**: Client connected, track shows as None

**Cause**: Web Audio API initialization delay

**Fix**: Add 1.5s delay after client detection

---

## Keep-Alive Pattern

### Agent Must Stay Alive

```python
# After session starts, keep agent alive
while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
    await asyncio.sleep(1.0)

logger.info("Agent session ended")
```

Without this, the entrypoint returns and the agent disconnects.

---

## Related Patterns

- `voice-agents/livekit-agents-1.3.x` - Overall integration
- `voice-agents/vad-tuning-recall-ai` - Audio detection sensitivity

---

## Anti-Memory Flag

Always verify participant identity patterns for your specific use case. The `output-media-` prefix is specific to Recall.ai integration.

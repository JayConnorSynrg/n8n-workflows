# VAD Tuning for Recall.ai Output Media

**Pattern ID**: `voice-agents/vad-tuning-recall-ai`
**Category**: Voice Agent Configuration
**Severity**: HIGH
**Created**: 2026-01-17
**Source**: Voice Agent POC debugging session

---

## Overview

Recall.ai Output Media provides processed/compressed audio that requires aggressive VAD (Voice Activity Detection) tuning. Default thresholds will fail to detect speech.

---

## The Problem

Standard Silero VAD defaults are optimized for high-quality microphone input:
- `activation_threshold=0.5` (default)
- `min_speech_duration=0.25` (250ms)

Recall.ai audio characteristics:
- Compressed/processed from meeting platforms
- Lower signal-to-noise ratio
- Variable audio levels
- May have additional latency

---

## Optimized VAD Configuration

```python
vad = silero.VAD.load(
    min_speech_duration=0.05,      # 50ms - faster speech detection start
    min_silence_duration=0.55,     # 550ms - natural end-of-turn detection
    prefix_padding_duration=0.5,   # 500ms - capture audio before speech onset
    activation_threshold=0.05,     # VERY LOW - critical for processed audio
    sample_rate=16000,             # Silero requires 8kHz or 16kHz
    force_cpu=True,                # Consistent CPU inference
)
```

### Parameter Breakdown

| Parameter | Default | Optimized | Rationale |
|-----------|---------|-----------|-----------|
| `activation_threshold` | 0.5 | 0.05 | Recall.ai audio is quieter/processed |
| `min_speech_duration` | 0.25s | 0.05s | Faster response to speech onset |
| `min_silence_duration` | 0.5s | 0.55s | Natural pause before end-of-turn |
| `prefix_padding_duration` | 0.3s | 0.5s | Capture start of utterance |
| `sample_rate` | 16000 | 16000 | Silero requirement |
| `force_cpu` | False | True | Predictable latency |

---

## Debugging Audio Levels

### Add Frame Monitoring

```python
@ctx.room.on("track_subscribed")
def on_track_subscribed(track, publication, participant):
    if track.kind == rtc.TrackKind.KIND_AUDIO:
        asyncio.create_task(count_audio_frames(track))

async def count_audio_frames(track):
    frame_count = 0
    silent_frames = 0
    max_rms = 0.0

    audio_stream = rtc.AudioStream(track)
    async for frame_event in audio_stream:
        frame_count += 1
        frame = frame_event.frame

        # Calculate RMS
        samples = frame.data
        if samples:
            num_samples = len(samples) // 2
            values = struct.unpack(f'{num_samples}h', samples[:num_samples*2])
            rms = (sum(v*v for v in values) / num_samples) ** 0.5
            if rms > max_rms:
                max_rms = rms
            if rms < 100:  # Very quiet
                silent_frames += 1

        # Log every 5 seconds
        if frame_count % 500 == 0:
            pct_silent = silent_frames / frame_count * 100
            max_db = 20 * math.log10(max_rms / 32767) if max_rms > 0 else -100

            logger.info(f"Audio stats: {frame_count} frames, {pct_silent:.1f}% silent")
            logger.info(f"Max RMS: {max_rms:.1f} ({max_db:.1f}dB)")

            if max_db < -50:
                logger.warning("AUDIO VERY QUIET - VAD may not trigger!")
```

### Interpreting Results

| Max dB | Diagnosis | Action |
|--------|-----------|--------|
| < -60 | No audio | Check track subscription |
| -60 to -50 | Very quiet | Lower threshold to 0.03 |
| -50 to -40 | Quiet | Threshold 0.05 should work |
| -40 to -20 | Normal | Default threshold may work |
| > -20 | Loud | Any threshold works |

---

## Common Failure Modes

### 1. Agent "Listening" But Never Responds

**Symptoms:**
- Agent logs show "listening" state
- User transcript events never fire
- Audio frames are flowing

**Cause:** VAD threshold too high for audio level

**Fix:** Lower `activation_threshold` to 0.05 or 0.03

### 2. Agent Interrupts Mid-Sentence

**Symptoms:**
- Agent responds before user finishes
- Choppy conversation flow

**Cause:** `min_silence_duration` too short

**Fix:** Increase to 0.55s or 0.6s

### 3. Missing Start of Utterances

**Symptoms:**
- Transcripts missing first word(s)
- STT shows incomplete phrases

**Cause:** `prefix_padding_duration` too short

**Fix:** Increase to 0.5s

---

## Tuning Methodology

### Progressive Threshold Reduction

Start with working values and adjust:

```
Initial:    activation_threshold=0.15
No trigger: activation_threshold=0.10
Still no:   activation_threshold=0.05
Still no:   activation_threshold=0.03
Still no:   Check audio subscription (not VAD issue)
```

### Sample Rate Verification

Silero VAD **only** supports:
- 8000 Hz
- 16000 Hz

Any other sample rate will cause silent failures. Verify input matches:

```python
audio_input=room_io.AudioInputOptions(
    sample_rate=16000,  # MUST match VAD expectation
    num_channels=1,
)
```

---

## Production Recommendations

1. **Always prewarm VAD** in `prewarm()` function
2. **Log audio statistics** at least every 30 seconds in production
3. **Set alerts** for >90% silent frames (indicates audio pipeline issue)
4. **Use `force_cpu=True`** for consistent latency (GPU inference adds variance)

---

## Related Patterns

- `voice-agents/livekit-agents-1.3.x` - Overall integration patterns
- `voice-agents/participant-detection` - Client audio subscription

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-17 | Initial pattern from debugging session |
| - | Threshold progression: 0.15 → 0.10 → 0.05 (final working value) |

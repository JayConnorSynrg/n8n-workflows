# LiveKit Agents TTS Research - Document Index

## Overview

Complete research on TTS (Text-to-Speech) and sentence chunking patterns from the livekit/agents repository (https://github.com/livekit/agents). All patterns extracted from battle-tested production code.

**Total documentation**: 4 comprehensive guides (48KB)
**Source analysis**: 8+ core files, 3 example implementations
**Languages analyzed**: NLTK (50+ languages), Python async patterns

---

## Document Guide

### 1. **LIVEKIT_TTS_QUICK_REFERENCE.md** (2.9 KB)
**Start here** - One-page reference with key metrics and quick lookup

**Contains**:
- Sentence segmentation method (NLTK punkt)
- Audio chunk sizing (200ms default)
- Stream pacing algorithm summary
- Buffer management overview
- Speed/tempo support status
- Performance targets
- File locations

**Best for**: Quick lookups, copying code patterns, understanding defaults

---

### 2. **LIVEKIT_TTS_PATTERNS.md** (13 KB)
**Core analysis document** - Detailed breakdown with code excerpts

**Contains**:
- Sentence tokenization approach (NLTK + whitespace concatenation)
- Stream processing with BufferedTokenStream
- Audio chunk sizing with sample rate calculations
- SentenceStreamPacer architecture with algorithm breakdown
- Channel-based buffering and segment signals
- Speed/tempo discussion (unsupported feature)
- Practical examples (2-word streaming, custom configs)
- Integration points with explanations
- Performance characteristics table
- Limitations and unsupported features
- Stream format and codec information

**Best for**: Understanding the underlying design, integration patterns, limitations

---

### 3. **LIVEKIT_TTS_CODE_SNIPPETS.md** (11 KB)
**Implementation reference** - Extracted and documented code

**Contains**:
- Sentence tokenization implementation (NLTK)
- Stream pacing algorithm (full _send_task method)
- Audio frame chunking (AudioEmitter.start)
- Buffered token stream (push_text, flush)
- Segment boundary management (_StartSegment, _EndSegment)
- Duration tracking code
- Complete integration example
- Configuration presets (aggressive/balanced/conservative)
- Raw PCM vs encoded detection logic
- Key constants reference

**Best for**: Copy-paste implementation, reference patterns, learning exact APIs

---

### 4. **LIVEKIT_TTS_ARCHITECTURE.md** (21 KB)
**Visual and structural reference** - Diagrams, flows, and data structures

**Contains**:
- ASCII audio pipeline flow (end-to-end)
- Concurrency architecture with async tasks
- Buffer state transitions (initial → ready → sending)
- Pacing decision tree (logic flow)
- Segment boundary data structures
- Duration calculation with timeline example
- Performance characteristics graphs
- Language support matrix
- Resource usage estimates
- Integration checklist

**Best for**: Understanding system architecture, presentation, high-level overview, troubleshooting

---

## Key Findings Summary

### Sentence Segmentation: NLTK Punkt (NOT Regex)
- Uses language-aware tokenizer, not regex patterns
- Default min length: 20 characters (configurable)
- Concatenates small sentences with spaces
- Supports 50+ languages including English, French, German, Spanish
- Does NOT support Chinese, Japanese, Korean (whitespace limitation)

### Audio Chunking: 200ms Frames
- Default frame size: 200ms
- At 24kHz: 4800 samples per frame
- Bytes per frame: ~9600 (stereo 16-bit) or ~4800 (mono)
- Frame size configurable but 200ms is recommended default

### Stream Pacing: Threshold-Based
- First sentence: send immediately (minimize latency)
- Subsequent: accumulate up to 300 chars OR when `remaining_audio <= 5.0 sec`
- Trigger: `remaining_audio = (audio_start_time + pushed_duration - current_time)`
- Prevents audio underruns and improves quality with context

### Buffer Management: Async Channels
- Input channel: text tokens + flush/end signals
- Processing: tokenize → batch → TTS → decode → frame
- Output: 200ms audio frames with metadata
- Segment boundaries: _StartSegment, _EndSegment, _FlushSegment

### Speed/Tempo: UNSUPPORTED
- Duration tracking exists but not used for speed adjustment
- Delegated entirely to TTS provider (Cartesia, OpenAI, ElevenLabs)
- No frame-level speed modification in framework

---

## Quick Lookup Table

| Question | Answer | Location |
|----------|--------|----------|
| How is text tokenized? | NLTK punkt tokenizer | PATTERNS (2.1) |
| What frame size? | 200ms default | QUICK_REF |
| How is pacing decided? | `remaining_audio <= 5.0s` | ARCHITECTURE (pacing tree) |
| First batch timing? | Immediate (no wait) | PATTERNS (3) |
| Min sentence length? | 20 chars | QUICK_REF |
| Max batch text? | 300 chars | QUICK_REF |
| Sample rate? | 24000 Hz typical | CODE_SNIPPETS (5) |
| Samples per frame? | 4800 at 24kHz, 200ms | PATTERNS (2) |
| Language support? | 50+ via NLTK | ARCHITECTURE (language matrix) |
| Speed adjustment? | Not implemented | PATTERNS (5) |
| Buffer type? | Async channels | PATTERNS (4) |
| File: tokenizer | nltk/sentence_tokenizer.py | PATTERNS (2.1) |
| File: pacing | tts/stream_pacer.py | PATTERNS (3) |
| File: audio | tts/tts.py | PATTERNS (2) |

---

## Implementation Paths

### Path 1: Minimal (Copy-Paste)
1. Copy SentenceTokenizer from CODE_SNIPPETS (1)
2. Copy SentenceStreamPacer from CODE_SNIPPETS (2)
3. Copy AudioEmitter from CODE_SNIPPETS (3)
4. Integrate with your TTS provider
5. Reference defaults from QUICK_REF

**Time estimate**: 2-3 hours
**Risk**: Low (proven code)

### Path 2: Learning (Study + Implement)
1. Read ARCHITECTURE overview
2. Study PATTERNS for design rationale
3. Review CODE_SNIPPETS for implementation details
4. Implement from scratch using patterns as guide
5. Validate against QUICK_REF

**Time estimate**: 4-6 hours
**Risk**: Medium (understand design decisions)

### Path 3: Deep Dive (Full Understanding)
1. Start with QUICK_REF for orientation
2. Read PATTERNS (full breakdown)
3. Study ARCHITECTURE (system design)
4. Review CODE_SNIPPETS (exact APIs)
5. Analyze source code in livekit/agents on GitHub
6. Implement custom variations

**Time estimate**: 8-12 hours
**Risk**: Low (comprehensive understanding)

---

## GitHub Source References

**Core TTS Files**:
- `livekit-agents/livekit/agents/tts/tts.py` - AudioEmitter, frame handling
- `livekit-agents/livekit/agents/tts/stream_pacer.py` - Pacing algorithm
- `livekit-agents/livekit/agents/tokenize/token_stream.py` - Buffered tokenization
- `livekit-plugins-nltk/livekit/plugins/nltk/sentence_tokenizer.py` - NLTK integration

**Example Files**:
- `examples/voice_agents/tts_text_pacing.py` - Text pacing example
- `examples/other/text-to-speech/cartesia_tts.py` - Cartesia streaming example
- `examples/voice_agents/realtime_with_tts.py` - Realtime TTS example

**Repository**: https://github.com/livekit/agents

---

## Key Metrics for n8n Implementation

```yaml
Audio Configuration:
  sample_rate: 24000
  channels: 1
  frame_size_ms: 200
  samples_per_frame: 4800

Text Processing:
  min_sentence_len: 20
  stream_context_len: 10
  min_token_len: 20
  max_batch_chars: 300

Pacing Thresholds:
  min_remaining_audio: 5.0  # seconds
  check_interval: 0.1       # seconds
  dispatch_on_first: true   # immediate for first batch

Performance Targets:
  latency_first_frame: 50-200ms
  frame_duration: 200ms
  max_overhead_cpu: 5%
  memory_per_stream: 260KB
```

---

## Testing Checklist

- [ ] Tokenize English text with min_sentence_len=20
- [ ] Verify concatenation of short sentences
- [ ] Test French/German language support
- [ ] Calculate frame count for 5-second audio
- [ ] Simulate remaining_audio threshold trigger
- [ ] Verify first sentence sends immediately
- [ ] Test batch accumulation up to 300 chars
- [ ] Validate async channel message order
- [ ] Confirm 200ms frame timing
- [ ] Test segment boundary signals
- [ ] Verify no speed adjustment in duration tracking
- [ ] Test graceful shutdown (end_input, aclose)

---

## Troubleshooting Quick Guide

| Problem | Cause | Solution |
|---------|-------|----------|
| First audio delayed | Not sending first sentence immediately | Check `first_sentence` logic in pacing |
| Audio underruns | min_remaining_audio too high | Reduce to 3-4 seconds |
| Large latency | max_text_length too large | Reduce to 150-200 chars |
| Poor quality | Sentence chunks too small | Increase min_sentence_len to 30+ |
| Memory bloat | Buffer not flushing | Call flush() after end_input() |
| Language not working | Not NLTK-supported | Check language support matrix |
| Wrong frame size | Sample rate mismatch | Verify: samples = rate // 1000 * ms |

---

## Document Statistics

| Document | Size | Sections | Code Examples |
|----------|------|----------|----------------|
| QUICK_REF | 2.9 KB | 8 | 3 |
| PATTERNS | 13 KB | 10 | 10+ |
| CODE_SNIPPETS | 11 KB | 9 | 25+ |
| ARCHITECTURE | 21 KB | 10 | diagrams |
| **Total** | **48 KB** | **37** | **40+** |

---

## Related n8n Documentation

**For TTS node development**:
- Consider: `/synrg-buildworkflow` for n8n-specific patterns
- Reference: `.claude/patterns/api-integration/` for similar patterns
- Check: `.claude/agents/n8n-node-validator.md` for validation rules

**For streaming audio**:
- See: WebRTC chunk handling in n8n voice nodes
- Review: Audio format conversion patterns
- Study: Real-time buffer management in n8n

---

## Next Steps

1. **For immediate use**: Use QUICK_REF + CODE_SNIPPETS
2. **For understanding**: Read PATTERNS + ARCHITECTURE
3. **For integration**: Review GitHub source files and examples
4. **For n8n nodes**: Adapt patterns to n8n node architecture
5. **For optimization**: Benchmark with your specific TTS provider

---

## Document Version Info

- **Created**: 2026-01-10
- **Research source**: livekit/agents main branch
- **Python version**: 3.10+
- **Dependencies**: nltk, asyncio, livekit-agents
- **Confidence level**: High (production code analysis)

---

**For questions or clarifications, refer to the specific document sections or GitHub source code directly.**

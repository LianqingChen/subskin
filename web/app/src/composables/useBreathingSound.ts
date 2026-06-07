import { ref } from 'vue'

export type SoundType = 'none' | 'bowl' | 'fish' | 'rain' | 'stream' | 'wind' | 'bird'

export const soundLabels: Record<SoundType, string> = {
  none: '静音',
  fish: '木鱼',
  bowl: '颂钵',
  rain: '雨声',
  stream: '溪流',
  wind: '风声',
  bird: '鸟鸣',
}

let audioCtx: AudioContext | null = null
let ambientNodes: AudioNode[] = []

function ctx(): AudioContext {
  if (!audioCtx) audioCtx = new AudioContext()
  if (audioCtx.state === 'suspended') audioCtx.resume()
  return audioCtx
}

function createNoiseBuffer(type: 'white' | 'pink' | 'brown'): AudioBuffer {
  const c = ctx()
  const sr = c.sampleRate
  const length = sr * 4
  const buffer = c.createBuffer(1, length, sr)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1

  if (type === 'pink') {
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0
    for (let i = 0; i < length; i++) {
      const w = data[i]
      b0 = 0.99886 * b0 + w * 0.0555179
      b1 = 0.99332 * b1 + w * 0.0750759
      b2 = 0.969 * b2 + w * 0.153852
      b3 = 0.8665 * b3 + w * 0.3104856
      b4 = 0.55 * b4 + w * 0.5329522
      b5 = -0.7616 * b5 - w * 0.016898
      data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11
      b6 = w * 0.115926
    }
  } else if (type === 'brown') {
    let last = 0
    for (let i = 0; i < length; i++) {
      data[i] = (last + 0.02 * data[i]) / 1.02
      last = data[i]
      data[i] *= 3.5
    }
  }

  return buffer
}

// ---- Single wooden fish beat ----

function scheduleFishBeat(c: AudioContext, t: number, vol = 1) {
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.type = 'sine'
  osc.frequency.value = 750
  gain.gain.setValueAtTime(0.12 * vol, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12)
  osc.connect(gain).connect(c.destination)
  osc.start(t)
  osc.stop(t + 0.12)

  const buf = createNoiseBuffer('white')
  const noise = c.createBufferSource()
  noise.buffer = buf
  const ng = c.createGain()
  const bp = c.createBiquadFilter()
  bp.type = 'bandpass'
  bp.frequency.value = 550
  bp.Q.value = 1.2
  ng.gain.setValueAtTime(0.08 * vol, t)
  ng.gain.exponentialRampToValueAtTime(0.001, t + 0.06)
  noise.connect(bp).connect(ng).connect(c.destination)
  noise.start(t)
  noise.stop(t + 0.06)
}

// ---- Phase cue sounds ----

function playBowl() {
  const c = ctx()
  const now = c.currentTime
  const freqs = [220, 440, 554, 660]
  freqs.forEach((f, i) => {
    const osc = c.createOscillator()
    const gain = c.createGain()
    osc.type = 'sine'
    osc.frequency.value = f * (1 + (Math.random() - 0.5) * 0.002)
    gain.gain.setValueAtTime(0.08 / (i + 1), now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 2.5)
    osc.connect(gain).connect(c.destination)
    osc.start(now)
    osc.stop(now + 2.5)
  })
}

// 木鱼节奏：吸气和屏息每秒一次，呼气每0.5秒一次
const fishPatterns: Record<number, number[]> = {
  0: [0, 1, 2, 3],                              // 吸气 4s：每秒一次
  1: [0, 1, 2, 3],                              // 屏息 4s：每秒一次
  2: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5], // 呼气 6s：每0.5秒一次
}

function playFishRhythm(phaseIndex: number) {
  const c = ctx()
  const now = c.currentTime
  const beats = fishPatterns[phaseIndex] || [0]
  beats.forEach((t, i) => {
    scheduleFishBeat(c, now + t, i === 0 ? 1.2 : 1)
  })
}

function playBird() {
  const c = ctx()
  const now = c.currentTime
  const count = 1 + Math.floor(Math.random() * 2)

  for (let j = 0; j < count; j++) {
    const t = now + j * 0.15
    const osc = c.createOscillator()
    const gain = c.createGain()
    osc.type = 'sine'
    const f0 = 1800 + Math.random() * 1200
    osc.frequency.setValueAtTime(f0, t)
    osc.frequency.linearRampToValueAtTime(f0 + 400 + Math.random() * 600, t + 0.06)
    osc.frequency.linearRampToValueAtTime(f0 - 200, t + 0.12)
    gain.gain.setValueAtTime(0, t)
    gain.gain.linearRampToValueAtTime(0.06, t + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15)
    osc.connect(gain).connect(c.destination)
    osc.start(t)
    osc.stop(t + 0.15)
  }
}

// ---- Ambient sounds ----

function startNoiseAmbient(type: 'rain' | 'stream' | 'wind') {
  const c = ctx()
  stopAmbient()

  const buf = createNoiseBuffer(type === 'stream' ? 'pink' : type === 'rain' ? 'pink' : 'white')
  const noise = c.createBufferSource()
  noise.buffer = buf
  noise.loop = true

  const filter = c.createBiquadFilter()
  const gain = c.createGain()

  if (type === 'rain') {
    filter.type = 'bandpass'
    filter.frequency.value = 2500
    filter.Q.value = 0.8
    gain.gain.value = 0.06
  } else if (type === 'stream') {
    filter.type = 'lowpass'
    filter.frequency.value = 1200
    gain.gain.value = 0.07
  } else {
    filter.type = 'lowpass'
    filter.frequency.value = 800
    gain.gain.value = 0.05
    const lfo = c.createOscillator()
    const lfoGain = c.createGain()
    lfo.type = 'sine'
    lfo.frequency.value = 0.15
    lfoGain.gain.value = 400
    lfo.connect(lfoGain).connect(filter.frequency)
    lfo.start()
    ambientNodes.push(lfo, lfoGain)
  }

  noise.connect(filter).connect(gain).connect(c.destination)
  noise.start()

  ambientNodes.push(noise, filter, gain)
}

function stopAmbient() {
  ambientNodes.forEach(n => {
    try { if (n instanceof AudioScheduledSourceNode) n.stop() } catch { /* already stopped */ }
    try { n.disconnect() } catch { /* already disconnected */ }
  })
  ambientNodes = []
}

// ---- Public API ----

export function useBreathingSound() {
  const current = ref<SoundType>('none')
  const showDropdown = ref(false)

  const ambientTypes: SoundType[] = ['rain', 'stream', 'wind']

  function setSound(type: SoundType) {
    stopAmbient()
    current.value = type
    showDropdown.value = false
    if (ambientTypes.includes(type)) startNoiseAmbient(type as 'rain' | 'stream' | 'wind')
  }

  function cuePhase(phaseIndex: number) {
    if (current.value === 'none') return
    if (current.value === 'bowl') playBowl()
    else if (current.value === 'fish') playFishRhythm(phaseIndex)
    else if (current.value === 'bird') playBird()
  }

  function cleanup() {
    stopAmbient()
    if (audioCtx) { audioCtx.close(); audioCtx = null }
  }

  return { current, showDropdown, soundLabels, setSound, cuePhase, cleanup }
}

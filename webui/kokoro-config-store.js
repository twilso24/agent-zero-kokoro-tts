import { createStore } from "/js/AlpineStore.js";

const VOICES = [
  { group: "American Female", voices: ["af_bella","af_nicole","af_sarah","af_sky"] },
  { group: "American Male", voices: ["am_adam","am_michael"] },
  { group: "British Female", voices: ["bf_alice","bf_emma","bf_isabella","bf_lily"] },
  { group: "British Male", voices: ["bm_george","bm_lewis"] },
  { group: "Chinese", voices: ["zf_xiaobei","zf_xiaoni","zf_xiaoxiao","zf_xiaoyi","zm_yunxi","zm_yunxia","zm_yunjian"] },
  { group: "French", voices: ["ff_siwis"] },
  { group: "Japanese", voices: ["jf_alpha","jf_gongitsune","jf_nezumi","jf_tebukuro","jm_kumo"] },
  { group: "Korean", voices: ["kf_danggeun","km_nihao"] },
  { group: "Hindi", voices: ["hf_alpha","hf_beta","hm_omega","hm_psi"] },
  { group: "Italian", voices: ["if_sara","im_nicola"] },
  { group: "Portuguese (BR)", voices: ["pf_dora","pm_alex","pm_santa"] },
  { group: "Spanish", voices: ["ef_dora","em_alex","em_santa"] },
  { group: "Arabic", voices: ["hf_alpha","hm_omega"] },
  { group: "Czech", voices: ["cf_libu\u0161e"] },
  { group: "Greek", voices: ["gf_l\u00e9da"] },
  { group: "Hungarian", voices: ["hf_lilla","hm_d\u00e1vid"] },
  { group: "Dutch", voices: ["hf_lotte","hm_willem"] },
];

const ALL_VOICES = VOICES.flatMap(g => g.voices);

const model = {
  mode: "single",
  slots: [
    { voice: "", weight: 0, enabled: true },
    { voice: "", weight: 0, enabled: false },
    { voice: "", weight: 0, enabled: false },
  ],
  voices: ALL_VOICES,
  groups: VOICES,

  onOpen(cfg) {
    if (!cfg) return;
    const voice = cfg.voice || "";
    if (voice.includes("*")) {
      this.mode = "blend";
      const parts = voice.split("+");
      parts.forEach((p, i) => {
        p = p.trim();
        if (!p || !p.includes("*")) return;
        const [w, v] = p.split("*", 2);
        if (i < 3) {
          this.slots[i].voice = v.trim();
          this.slots[i].weight = parseFloat(w) || 0;
          this.slots[i].enabled = true;
        }
      });
    } else if (voice.includes(",")) {
      this.mode = "manual";
    } else {
      this.mode = "single";
    }
  },

  applyMode(config) {
    if (this.mode === "single") {
      if (!config.voice || config.voice.includes("*") || config.voice.includes(",")) {
        config.voice = ALL_VOICES[0];
      }
    } else if (this.mode === "manual") {
      if (!config.voice || !config.voice.includes(",")) {
        config.voice = "af_bella,bf_emma";
      }
    } else {
      this._writeBlend(config);
    }
  },

  setSlotVoice(index, voice, config) {
    this.slots[index].voice = voice;
    if (this.mode === "blend") this._writeBlend(config);
  },

  setSlotWeight(index, weight, config) {
    this.slots[index].weight = parseFloat(weight) || 0;
    if (this.mode === "blend") this._writeBlend(config);
  },

  toggleSlot(index, enabled, config) {
    this.slots[index].enabled = enabled;
    if (this.mode === "blend") this._writeBlend(config);
  },

  _writeBlend(config) {
    const active = this.slots.filter(s => s.enabled && s.voice && s.weight > 0);
    if (active.length === 0) {
      config.voice = "";
      return;
    }
    const parts = active.map(s => `${s.weight.toFixed(2)}*${s.voice}`);
    config.voice = parts.join(" + ");
  },

  get blendStatus() {
    if (this.mode !== "blend") return "";
    const active = this.slots.filter(s => s.enabled && s.voice && s.weight > 0);
    const sum = active.reduce((a, s) => a + s.weight, 0);
    if (active.length === 0) return "⚠ add at least one voice";
    if (Math.abs(sum - 1.0) > 0.01) return `⚠ weights sum to ${sum.toFixed(2)} (need 1.0)`;
    return "✓ ready";
  },

  cleanup() {},
};

export const store = createStore("kokoroBlend", model);

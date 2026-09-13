export const MOTION = Object.freeze({
  micro: 0.18,
  standard: 0.3,
  content: 0.55,
  page: 0.3,
  modalOverlay: 0.24,
  modalContent: 0.3,
  loadingIntro: 0.3,
  loadingIcon: 2.1,
  loadingDots: 1.1,
})

export const MOTION_EASE = 'easeOut'

export function motionTransition(duration = MOTION.standard, delay = 0) {
  return { duration, delay, ease: MOTION_EASE }
}

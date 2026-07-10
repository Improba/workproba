import { computed } from 'vue'

export const defaultMastokProps = {
  secondary: { type: Boolean, default: false },
  tertiary: { type: Boolean, default: false },
  light: { type: Boolean, default: false },
  danger: { type: Boolean, default: false },
  success: { type: Boolean, default: false },
  warning: { type: Boolean, default: false },
  flat: { type: Boolean, default: false },

  lucideIcon: { type: String, default: null }
}

export interface IMastokProps {
  secondary?: boolean
  tertiary?: boolean
  light?: boolean
  success?: boolean
  warning?: boolean
  danger?: boolean

  flat?: boolean
  lucideIcon?: string
}

export const useMastok = (props: IMastokProps) => {

  const colorInfos = computed(() => {
    const infos = {
      color: '',
      border: '',
      text: '',
    }

    switch (true) {
      case props.secondary:
        infos.color = 'bg-neutral-lowest'
        infos.border = 'border-primary-thin'
        infos.text = 'text-primary'
        break

      case props.tertiary:
        infos.color = props.flat ? 'bg-neutral-high' : 'bg-neutral-lowest'
        infos.border = 'border-neutral-low-thin'
        infos.text = 'text-neutral-high'
        break

      case props.light:
        infos.color = 'bg-neutral-higher'
        infos.border = 'border-neutral-high-thin'
        infos.text = 'text-neutral-lowest'
        break

      case props.danger:
        infos.color = 'bg-danger'
        infos.border = 'border-danger-thin'
        infos.text = 'text-neutral-lowest'
        break

      case props.success:
        infos.color = 'bg-success'
        infos.border = 'border-success-thin'
        infos.text = 'text-neutral-lowest'
        break

      case props.warning:
        infos.color = 'bg-warning'
        infos.border = 'border-warning-thin'
        infos.text = 'text-neutral-lowest'
        break

      // Primary
      default:
        infos.color = 'bg-primary'
        infos.border = 'border-primary-thin'
        infos.text = 'text-neutral-lowest'
        break
    }

    return infos
  })

  return {
    colorInfos
  }
}

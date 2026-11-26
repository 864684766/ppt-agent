import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// shadcn/ui 风格的基础按钮：样式属于项目，可随产品需求调整。
const buttonVariants = cva('ui-button', { variants: { variant: { default: 'button-default', outline: 'button-outline', ghost: 'button-ghost' }, size: { default: 'button-size-default', icon: 'button-size-icon' } }, defaultVariants: { variant: 'default', size: 'default' } })
type ButtonProps = React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }
export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return <Component className={cn(buttonVariants({ variant, size, className }))} {...props} />
}

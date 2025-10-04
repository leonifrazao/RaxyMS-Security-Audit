'use client'

import { useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, Plus } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { toast } from '@/hooks/use-toast'
import { useAddAccountMutation } from '@/features/accounts/hooks/use-accounts'

const schema = z.object({
  email: z.string().email('Informe um e-mail válido.'),
  password: z.string().min(6, 'A senha deve conter pelo menos 6 caracteres.'),
  proxy: z
    .string()
    .trim()
    .optional()
    .transform((value) => (value ? value : undefined)),
})

export type AddAccountFormValues = z.infer<typeof schema>

interface AddAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AddAccountDialog({ open, onOpenChange }: AddAccountDialogProps) {
  const form = useForm<AddAccountFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: '',
      password: '',
      proxy: undefined,
    },
  })

  const addAccount = useAddAccountMutation()

  useEffect(() => {
    if (!open) {
      form.reset()
    }
  }, [open, form])

  const onSubmit = async (values: AddAccountFormValues) => {
    try {
      await addAccount.mutateAsync(values)
      toast({
        title: 'Conta adicionada',
        description: 'A conta foi adicionada e será sincronizada em instantes.',
      })
      onOpenChange(false)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Não foi possível adicionar a conta.'
      toast({
        title: 'Erro ao adicionar conta',
        description: message,
        variant: 'destructive',
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Adicionar nova conta</DialogTitle>
          <DialogDescription>
            Informe as credenciais da conta Microsoft Rewards e, se necessário, a configuração de proxy.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>E-mail</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" placeholder="conta@exemplo.com" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Senha</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" placeholder="********" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="proxy"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Proxy (opcional)</FormLabel>
                  <FormControl>
                    <Input placeholder="http://usuario:senha@host:porta" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={addAccount.isPending}>
                  Cancelar
                </Button>
              </DialogClose>
              <Button type="submit" disabled={addAccount.isPending}>
                {addAccount.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    Salvando
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" aria-hidden />
                    Adicionar conta
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

import random
import string
import time
from raxy_project.raxy.api.mail_tm_api import MailTm, MailTmError

def generate_random_string(length=10):
    """Gera uma string aleatória para nomes de usuário e senhas."""
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

def main():
    """Função principal para demonstrar o uso da API Mail.tm."""
    api = MailTm()

    try:
        # 1. Obter um domínio disponível
        domains = api.get_domains()
        if not domains:
            print("Não foi possível obter domínios. Saindo.")
            return
        
        domain = domains[0]['domain']
        print(f"✔️ Domínio selecionado: {domain}")

        # 2. Gerar credenciais aleatórias
        username = generate_random_string()
        password = generate_random_string(12)
        email_address = f"{username}@{domain}"
        
        print(f"📧 E-mail gerado: {email_address}")
        print(f"🔑 Senha gerada: {password}")

        # 3. Criar uma nova conta
        api.create_account(email_address, password)
        print(f"✔️ Conta criada com sucesso para {api.address} com ID: {api.account_id}")
        
        # 4. Verificar a caixa de entrada
        print("\n⏳ Aguardando a chegada de e-mails... (Verificando por 60 segundos)")
        start_time = time.time()
        found_message = False
        
        while time.time() - start_time < 60:
            messages = api.get_messages()
            
            if messages:
                print(f"\n🎉 E-mail recebido! Total: {len(messages)}")
                
                # 5. Obter detalhes do primeiro e-mail
                first_message = messages[0]
                message_id = first_message['id']
                
                print(f"  - De: {first_message['from']['address']}")
                print(f"  - Assunto: {first_message['subject']}")
                print(f"  - Prévia: {first_message['intro']}")
                
                # 6. Ler o conteúdo completo do e-mail
                full_message = api.get_message(message_id)
                print("\n📜 Conteúdo completo do e-mail (texto):")
                print(full_message.get('text') or "Nenhum conteúdo em texto simples.")
                
                # 7. Marcar o e-mail como lido
                api.mark_message_as_seen(message_id)
                print(f"\n✔️ Mensagem {message_id} marcada como lida.")
                found_message = True
                break
            else:
                print(".", end="", flush=True)
                time.sleep(5)
        
        if not found_message:
            print("\n❌ Nenhum e-mail recebido no tempo limite.")

    except MailTmError as e:
        print(f"\nOcorreu um erro com a API: {e}")
    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
    finally:
        # 8. Excluir a conta para limpeza
        if api.token and api.account_id:
            print("\n🧹 Limpando... Excluindo a conta.")
            try:
                api.delete_account()
                print("✔️ Conta excluída com sucesso.")
            except MailTmError as e:
                print(f"Falha ao excluir a conta: {e}")

if __name__ == "__main__":
    main()
# Troubleshooting — Acessos e Login — MedSys ERP Hospitalar

Este guia cobre os problemas mais comuns relacionados a login, permissões e bloqueios de acesso, com passos de investigação para a equipe de suporte.

---

## Usuário não consegue fazer login

### Passo 1 — Verificar status do usuário

Acesse **Configurações > Usuários** (requer perfil Administrador) e localize o usuário pelo nome ou e-mail. Verifique o campo **Status**:

- **Ativo** — login deveria funcionar normalmente
- **Inativo** — usuário foi desativado manualmente (geralmente por desligamento ou afastamento). Reativação requer perfil Administrador
- **Bloqueado por tentativas** — ver Passo 2

### Passo 2 — Verificar bloqueio por tentativas inválidas

O sistema bloqueia automaticamente o login após **5 tentativas consecutivas com senha incorreta**, em uma janela de 15 minutos.

Quando bloqueado:

- O campo **Bloqueado até** mostra o horário em que o bloqueio expira automaticamente (30 minutos após a 5ª tentativa)
- Um Administrador pode **desbloquear manualmente** antes desse prazo, no botão **Desbloquear Agora** na tela de detalhes do usuário

### Passo 3 — Verificar histórico de tentativas

Em **Configurações > Usuários > [usuário] > Histórico de Acessos**, é possível ver:

- Data/hora de cada tentativa
- IP de origem
- Resultado (sucesso ou falha)
- Motivo da falha, quando aplicável (senha incorreta, usuário inativo, sessão expirada)

Esse histórico é útil para identificar se o problema é senha esquecida (várias falhas seguidas do mesmo IP) ou possível tentativa de acesso indevido (falhas de IPs diferentes).

### Passo 4 — Verificar expiração de senha

Por política padrão, senhas expiram a cada **90 dias**. Se o campo **Senha expira em** já passou, o usuário verá uma tela de redefinição obrigatória no próximo login — isso não é um erro, é o comportamento esperado. Caso o usuário relate uma tela "diferente do normal" pedindo nova senha, é provável que seja isso.

---

## "Sessão expirada" frequente

Por padrão, sessões inativas expiram após **30 minutos sem interação**. Isso é configurável em **Configurações > Segurança > Tempo de Sessão**, mas reduzir muito esse valor pode gerar reclamações de usuários que demoram para preencher prontuários.

Se o problema ocorre mesmo com uso ativo do sistema, possíveis causas:

- Múltiplas abas/janelas abertas com o mesmo usuário (o sistema permite apenas **uma sessão ativa por usuário** por padrão; abrir uma segunda aba encerra a primeira)
- Configuração de **"Sessão única por IP"** ativada (em **Configurações > Segurança**), que pode causar conflitos em redes com IP compartilhado/NAT

---

## "Acesso negado" ao tentar abrir um módulo

Esse erro indica que o **perfil do usuário não tem permissão** para aquele módulo específico, não que há um problema técnico.

1. Verifique o perfil do usuário em **Configurações > Usuários > [usuário] > Perfil**
2. Compare com a tabela de perfis e acessos (disponível no FAQ Geral)
3. Se o usuário deveria ter acesso, um Administrador precisa ajustar o perfil ou conceder uma **permissão individual adicional** em **Configurações > Usuários > [usuário] > Permissões Extras**

Permissões individuais extras sobrepõem o perfil padrão, mas **não removem** restrições — apenas adicionam acessos extras a um perfil existente.

---

## Usuário vê dados de outra unidade/filial

O MedSys suporta múltiplas unidades (filiais) sob a mesma instância. Cada usuário é vinculado a uma ou mais unidades em **Configurações > Usuários > [usuário] > Unidades Vinculadas**.

Se um usuário está vendo pacientes ou agendamentos de uma unidade que não deveria:

1. Verifique as **Unidades Vinculadas** do usuário
2. Verifique se o usuário está com a unidade correta selecionada no seletor de unidade (canto superior, ao lado do nome do usuário) — usuários vinculados a múltiplas unidades podem alternar entre elas, e às vezes o problema é apenas a unidade ativa errada na sessão atual

---

## Erro "Token de autenticação inválido" (na versão mobile/web responsiva)

Esse erro costuma ocorrer quando:

- O usuário trocou a senha em outro dispositivo (todos os tokens anteriores são invalidados por segurança)
- O aplicativo/navegador ficou muito tempo em segundo plano e o token expirou (validade padrão: 24h)

Solução: fazer logout completo e login novamente. Se o erro persistir após login novo, verificar se o relógio do dispositivo está sincronizado corretamente — tokens JWT são sensíveis a diferenças de horário entre cliente e servidor maiores que 5 minutos.

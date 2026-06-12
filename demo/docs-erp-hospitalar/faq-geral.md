# Perguntas Frequentes — MedSys ERP Hospitalar

## Geral

### Como faço para alterar a senha do meu usuário?

Acesse o ícone de perfil no canto superior direito e clique em **Minha Conta > Alterar Senha**. Por política de segurança, a senha deve ter no mínimo 8 caracteres, incluindo letras e números, e não pode repetir as últimas 5 senhas utilizadas.

### Esqueci minha senha. O que fazer?

Na tela de login, clique em **Esqueci minha senha**. Um link de redefinição será enviado ao e-mail cadastrado no seu usuário. O link expira em 30 minutos. Se o e-mail cadastrado estiver desatualizado, contate o Administrador do sistema na sua unidade — apenas o Administrador pode alterar o e-mail vinculado a outro usuário.

### Posso acessar o sistema pelo celular?

Sim. O MedSys possui versão web responsiva, acessível por navegador no celular. As funcionalidades de **Agendamento** e **Consulta de Prontuário (somente leitura)** estão disponíveis na versão mobile. Funções de **Faturamento** e **Configurações Administrativas** estão disponíveis apenas na versão desktop.

---

## Permissões e Perfis de Acesso

### Quais são os perfis de usuário disponíveis?

| Perfil | Acesso típico |
|---|---|
| Recepção | Cadastro de pacientes, agendamento |
| Enfermagem | Prontuário (evoluções), agendamento |
| Médico | Prontuário completo, prescrições, agendamento próprio |
| Faturamento | Módulo de Faturamento, relatórios financeiros |
| Supervisor | Todos os módulos operacionais, relatórios gerenciais |
| Administrador | Acesso total, incluindo configurações do sistema e gestão de usuários |
| Diretoria Clínica | Acesso total a prontuários, incluindo prontuários bloqueados |
| Auditoria | Acesso de leitura a todos os módulos, incluindo logs de auditoria |

### Como solicitar mudança de perfil de um usuário?

Apenas o perfil **Administrador** pode alterar perfis de outros usuários, em **Configurações > Usuários > Editar**. Caso sua unidade não tenha um Administrador disponível, abra um chamado com o suporte indicando o nome do usuário e o novo perfil desejado.

---

## Notificações

### O sistema envia lembretes de consulta para os pacientes?

Sim, se configurado. Em **Configurações > Notificações**, é possível ativar lembretes automáticos por SMS e/ou e-mail, configuráveis para disparar 24h e/ou 2h antes do horário agendado. Essa configuração é por unidade, não por paciente individual.

### Por que alguns pacientes não recebem notificações mesmo com a configuração ativada?

As causas mais comuns são:

- Telefone ou e-mail do paciente não cadastrado ou inválido
- Paciente optou por **não receber notificações** (campo "Aceita notificações" em Pacientes > Detalhes, marcado como "Não")
- Limite mensal de envios de SMS da unidade foi atingido (verifique em **Configurações > Notificações > Consumo do Mês**)

---

## Relatórios

### Onde encontro relatórios de produtividade por profissional?

Em **Relatórios > Produtividade**, é possível filtrar por profissional, especialidade e período. O relatório mostra: total de atendimentos, taxa de absenteísmo (faltas), tempo médio de consulta e total faturado (se o usuário tiver permissão de Faturamento).

### Os relatórios podem ser exportados?

Sim, em formato PDF ou XLSX, pelo botão **Exportar** disponível no canto superior direito de cada relatório. Relatórios muito grandes (acima de 10.000 linhas) são processados em segundo plano e enviados por e-mail ao usuário quando concluídos.

---

## Integrações

### O MedSys integra com sistemas de laboratório externos?

Sim, via integração **HL7** (padrão internacional de troca de informações em saúde) ou por importação manual de arquivo. A configuração de integração com laboratórios é feita em **Configurações > Integrações > Laboratórios**, e requer dados técnicos fornecidos pelo laboratório parceiro (endpoint, credenciais).

### É possível integrar com a Receita Federal para emissão de notas fiscais de serviço?

A emissão de **Nota Fiscal de Serviço Eletrônica (NFS-e)** é feita pelo módulo de Faturamento, com integração à prefeitura do município (cada município tem seu próprio sistema de NFS-e). A configuração depende do município onde a unidade está cadastrada — consulte **Configurações > Faturamento > NFS-e** para verificar se o município da sua unidade já está homologado.

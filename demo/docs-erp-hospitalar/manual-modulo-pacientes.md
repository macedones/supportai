# Módulo de Pacientes — MedSys ERP Hospitalar

## Visão Geral

O módulo de Pacientes é o ponto central de cadastro e consulta de informações dos pacientes atendidos pela instituição. Todo atendimento, agendamento, internação ou faturamento depende de um cadastro de paciente válido neste módulo.

---

## Cadastro de Paciente

### Campos obrigatórios

- **Nome completo**
- **CPF** (ou CNS — Cartão Nacional de Saúde, para pacientes sem CPF)
- **Data de nascimento**
- **Sexo**
- **Nome da mãe**

### Campos recomendados (não bloqueiam o cadastro, mas geram alertas)

- Telefone de contato
- E-mail
- Endereço completo
- Convênio vinculado

### Como cadastrar um novo paciente

1. Acesse **Pacientes > Novo Cadastro**
2. Preencha os campos obrigatórios
3. Caso o paciente já possua convênio, clique em **Vincular Convênio** e informe o número da carteirinha
4. Clique em **Salvar**

O sistema gera automaticamente um **Número de Prontuário (NP)** sequencial, único por unidade hospitalar. Esse número é a referência principal usada em todos os outros módulos (Agendamento, Internação, Faturamento).

---

## Busca de Pacientes

A busca pode ser feita por:

- Nome (busca parcial, sem distinção de maiúsculas/minúsculas)
- CPF
- Número de Prontuário (NP)
- Cartão Nacional de Saúde (CNS)
- Data de nascimento

### Pacientes duplicados

O sistema possui um alerta automático de **possível duplicidade de cadastro**, disparado quando:

- Mesmo CPF já existe no sistema, OU
- Mesmo nome completo + data de nascimento já existem

Quando esse alerta aparece, **não crie um novo cadastro**. Em vez disso:

1. Use a busca para localizar o cadastro existente
2. Se o cadastro existente estiver desatualizado, edite-o
3. Caso haja dois cadastros duplicados já criados, utilize **Pacientes > Unificar Cadastros** (disponível apenas para perfis Administrador e Supervisor)

A unificação de cadastros é uma operação irreversível e move todo o histórico (atendimentos, exames, faturamento) do cadastro secundário para o cadastro principal escolhido.

---

## Prontuário Eletrônico

O prontuário consolida:

- Histórico de atendimentos
- Exames realizados e resultados
- Prescrições médicas
- Evoluções de enfermagem
- Alergias e condições registradas

### Status do prontuário

| Status | Significado |
|---|---|
| Ativo | Paciente com cadastro normal, prontuário acessível |
| Bloqueado | Prontuário temporariamente bloqueado (ex.: pendência de documentação, decisão judicial, óbito em processamento) |
| Arquivado | Paciente sem atendimentos há mais de 5 anos; prontuário movido para armazenamento de longo prazo |

**Importante:** prontuários com status **Bloqueado** não podem ser editados nem visualizados por perfis comuns. Apenas o perfil **Diretoria Clínica** ou **Auditoria** pode liberar temporariamente o acesso, registrando o motivo no log de auditoria.

---

## Erros Comuns

### "CPF já cadastrado no sistema"

Significa que já existe um paciente com esse CPF. Use a busca por CPF antes de tentar um novo cadastro.

### "Não é possível salvar: campo Nome da Mãe obrigatório"

Em alguns estados, o campo Nome da Mãe é obrigatório por exigência do Ministério da Saúde para integração com o CNES (Cadastro Nacional de Estabelecimentos de Saúde). Caso o paciente não saiba informar, utilize "Não Informado" — o sistema aceita esse valor padrão.

### "Prontuário bloqueado para edição"

Verifique o status do prontuário em **Pacientes > Detalhes > Status**. Se estiver como "Bloqueado", a liberação deve ser solicitada à Diretoria Clínica ou à Auditoria.

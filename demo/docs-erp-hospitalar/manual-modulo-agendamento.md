# Módulo de Agendamento — MedSys ERP Hospitalar

## Visão Geral

O módulo de Agendamento gerencia a marcação de consultas, exames e procedimentos, controlando a disponibilidade de profissionais, salas e equipamentos.

---

## Tipos de Agendamento

- **Consulta** — atendimento médico ambulatorial
- **Exame** — procedimentos diagnósticos (laboratoriais, imagem, etc.)
- **Procedimento** — pequenas cirurgias, curativos, infusões
- **Retorno** — consulta de acompanhamento vinculada a um atendimento anterior

---

## Como Agendar uma Consulta

1. Acesse **Agendamento > Nova Marcação**
2. Localize o paciente pelo Número de Prontuário (NP) ou CPF
3. Selecione a especialidade desejada
4. Escolha o profissional (ou deixe em branco para "Qualquer profissional disponível")
5. Selecione data e horário disponíveis na agenda
6. Confirme

O sistema valida automaticamente:

- Se o paciente já possui agendamento no mesmo horário (conflito de agenda do paciente)
- Se o profissional está disponível naquele horário (conflito de agenda do profissional)
- Se a sala/consultório está livre (conflito de recurso)

---

## Conflitos de Agenda

### "Paciente já possui agendamento neste horário"

O sistema bloqueia agendamentos duplicados para o mesmo paciente no mesmo intervalo de tempo. Para resolver:

1. Verifique a agenda do paciente em **Pacientes > Detalhes > Agendamentos**
2. Cancele o agendamento conflitante (se for engano), ou
3. Escolha outro horário

### "Profissional indisponível neste horário"

Pode ocorrer por três motivos:

1. **Agenda já preenchida** — o profissional já tem outro paciente nesse horário
2. **Bloqueio de agenda** — o profissional registrou um período de indisponibilidade (férias, congresso, plantão em outra unidade)
3. **Fora do expediente configurado** — o horário solicitado está fora da janela de atendimento cadastrada para aquele profissional

Para verificar o motivo exato, acesse **Agendamento > Agenda do Profissional** e visualize o dia em questão. Bloqueios aparecem em cinza, com o motivo ao passar o mouse.

### "Sala/recurso indisponível"

Salas e equipamentos (ex.: sala de exame, equipamento de raio-X) também possuem agenda própria. Se duas especialidades tentarem usar o mesmo recurso no mesmo horário, o sistema bloqueia a segunda marcação.

Administradores podem reconfigurar a alocação de salas em **Configurações > Recursos e Salas**.

---

## Cancelamento e Reagendamento

- Cancelamentos com **mais de 24h de antecedência** não geram nenhum registro adicional
- Cancelamentos com **menos de 24h de antecedência** são marcados automaticamente como **"Cancelamento Tardio"** e contam em relatórios de absenteísmo
- **Faltas (no-show)**: quando o paciente não comparece e o profissional marca "Não Compareceu", o sistema registra a falta no histórico do paciente. Pacientes com 3 ou mais faltas em 90 dias recebem um alerta visual no momento de novos agendamentos, mas isso **não bloqueia** novas marcações — é apenas informativo.

---

## Lista de Espera

Quando não há horários disponíveis para uma especialidade, o paciente pode ser adicionado à **Lista de Espera** (botão disponível na tela de Nova Marcação quando nenhum horário é encontrado).

Quando um horário é liberado (por cancelamento, por exemplo), o sistema notifica automaticamente os pacientes da lista de espera **por ordem de inclusão**, via SMS ou e-mail (configurável em **Configurações > Notificações**).

---

## Erros Comuns

### "Não é possível agendar: paciente com prontuário bloqueado"

Veja a documentação do Módulo de Pacientes sobre status de prontuário. Um prontuário bloqueado impede novos agendamentos até que a Diretoria Clínica ou Auditoria libere o acesso.

### "Horário selecionado não está mais disponível"

Pode acontecer quando dois usuários tentam agendar o mesmo horário simultaneamente. O sistema atribui o horário ao primeiro que confirmar; o segundo recebe esse aviso e precisa escolher outro horário.

### "Especialidade não configurada para este profissional"

O profissional selecionado não está vinculado àquela especialidade em seu cadastro. Verifique em **Configurações > Profissionais > Especialidades Vinculadas**.

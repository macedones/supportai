# Módulo de Faturamento — MedSys ERP Hospitalar

## Visão Geral

O módulo de Faturamento gerencia a cobrança de atendimentos, sejam particulares ou via convênios médicos, incluindo a geração de guias no padrão **TISS** (Troca de Informação em Saúde Suplementar) exigido pela ANS.

---

## Tipos de Atendimento para Faturamento

- **Particular** — pago diretamente pelo paciente
- **Convênio** — faturado contra uma operadora de saúde
- **SUS** — faturado via sistema público (integração com SIGTAP/DATASUS)

---

## Fluxo de Faturamento por Convênio

1. Atendimento é realizado e registrado pelo profissional (consulta, exame ou procedimento)
2. O sistema gera automaticamente um **lançamento de faturamento pendente**
3. O setor de faturamento revisa o lançamento em **Faturamento > Lançamentos Pendentes**
4. Lançamentos são agrupados em **Lotes de Guias TISS**
5. Lotes são exportados (XML) e enviados à operadora
6. A operadora retorna um **demonstrativo de pagamento**, que pode conter glosas

---

## Glosas

**Glosa** é a recusa, total ou parcial, de pagamento por parte da operadora de saúde, geralmente por inconsistência na guia.

### Tipos de Glosa

| Tipo | Descrição | Ação recomendada |
|---|---|---|
| Glosa administrativa | Erro de preenchimento (código de procedimento incorreto, dados do paciente divergentes) | Corrigir e reenviar (recurso de glosa) |
| Glosa técnica | Operadora questiona a pertinência clínica do procedimento | Anexar justificativa médica e laudo, enviar recurso |
| Glosa por elegibilidade | Paciente sem cobertura ativa na data do atendimento | Verificar carência/vigência do convênio antes de novo recurso |

### Como tratar uma Glosa

1. Acesse **Faturamento > Glosas**
2. Localize a guia glosada pelo número do lote ou nome do paciente
3. Verifique o **código de motivo da glosa** retornado pela operadora (campo "Motivo TISS")
4. Se for glosa administrativa, corrija o campo indicado e clique em **Reenviar**
5. Se for glosa técnica, anexe documentação médica em **Anexar Recurso** e envie para análise

O prazo para recurso de glosa varia por operadora, geralmente entre 30 e 90 dias corridos a partir do recebimento do demonstrativo. O sistema exibe um alerta em **Faturamento > Glosas Próximas do Prazo** quando faltam menos de 10 dias.

---

## Validação de Carteirinha de Convênio

Antes de cada atendimento, o sistema pode validar a carteirinha do convênio em tempo real, caso a operadora ofereça **integração TISS de elegibilidade**.

### Status possíveis

- **Elegível** — atendimento pode prosseguir normalmente
- **Não elegível** — carência não cumprida ou plano suspenso; sistema exibe alerta mas **não bloqueia** o atendimento (decisão fica com a recepção/financeiro)
- **Operadora indisponível** — falha temporária na integração; sistema permite seguir com validação manual

---

## Tabelas de Procedimentos

O sistema utiliza três tabelas de referência configuráveis em **Configurações > Tabelas de Procedimentos**:

- **TUSS** (Terminologia Unificada da Saúde Suplementar) — padrão para convênios
- **CBHPM** (Classificação Brasileira Hierarquizada de Procedimentos Médicos) — usada para cálculo de honorários médicos
- **SIGTAP** — tabela do SUS

Cada procedimento cadastrado no sistema deve ter pelo menos um código TUSS vinculado para permitir faturamento por convênio.

---

## Erros Comuns

### "Procedimento sem código TUSS vinculado"

O procedimento foi registrado no atendimento, mas não possui correspondência na tabela TUSS. Vá em **Configurações > Tabelas de Procedimentos > TUSS** e vincule o código correto antes de gerar o lote de faturamento.

### "Convênio não permite faturamento direto — apenas reembolso"

Alguns convênios (geralmente seguros de saúde, não operadoras tradicionais) não recebem faturamento direto da instituição. Nesse caso, o atendimento deve ser registrado como **Particular**, e o sistema gera automaticamente um **recibo para reembolso** que o paciente pode enviar à sua seguradora.

### "Lote TISS rejeitado: erro de schema XML"

Geralmente indica que a versão do padrão TISS configurada no sistema (em **Configurações > TISS > Versão do Padrão**) está desatualizada em relação ao que a operadora exige. Verifique a versão exigida pela operadora (geralmente divulgada no portal da ANS) e atualize a configuração.

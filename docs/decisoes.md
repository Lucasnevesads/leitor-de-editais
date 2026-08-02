# Decisões do projeto

Registro do **porquê**, não do que foi feito. O código já mostra o que foi feito.

---

## Um contrato de extração, dois extratores

**A escolha:** todo extrator devolve o mesmo formato (`contrato.CAMPOS`, cada campo com status, valor e trecho), e a conferência (`contrato.validar`) roda igual sobre qualquer um. O extrator por regras é o padrão; o por modelo é opcional e fica atrás de `--extrator modelo`.

**Por quê:** o valor do projeto não está em chamar uma API, está no que se exige de qualquer resposta antes de ela virar parecer. Com o contrato no meio, trocar de extrator (ou trocar o modelo de IA) não muda uma linha da conferência nem do parecer. E o padrão é o de regras porque quem clona o repositório precisa ver o projeto funcionando sem chave, sem custo e sem internet.

**O que custa:** o extrator por regras só entende edital que segue a estrutura usual da Lei 14.133/2021. Redação fora do padrão vira `nao_encontrado`, nunca um chute. É o extrator por modelo que existe para esse caso, e é uma troca honesta: o de regras erra por omissão, o de modelo pode errar por invenção.

---

## Campo não encontrado é diferente de campo vazio

**A escolha:** três status, não dois. `encontrado` (o edital responde), `ausente_declarado` (o edital diz que não exige) e `nao_encontrado` (o edital silencia). O parecer trata cada um de um jeito: valor, certeza registrada e pergunta a fazer ao órgão.

**Por quê:** "não será exigida garantia de proposta" e a ausência de qualquer menção à garantia de proposta produzem o mesmo campo vazio num formulário, mas são informações opostas: uma dispensa a corretora de agir, a outra exige uma ligação antes de cotar. Um parecer que funde os dois transforma silêncio em resposta, e esse é exatamente o tipo de erro que não aparece até custar caro.

**O que custa:** o `ausente_declarado` exige prova (a frase que declara a ausência), então o extrator precisa reconhecer a declaração, não só a presença. Fórmulas de dispensa fora do padrão caem para `nao_encontrado`, o que é o lado seguro do erro: vira pergunta, não certeza.

---

## O trecho é prova, e prova se confere

**A escolha:** todo campo `encontrado` carrega o trecho literal do edital de onde o valor saiu, e a conferência verifica que o trecho existe mesmo no texto. No extrator por modelo, campo com trecho que não consta do edital é rebaixado para `nao_encontrado`, com o problema anotado no parecer.

**Por quê:** o modo de falha perigoso de um extrator por modelo não é o JSON quebrado, é o valor plausível com origem inventada. Exigir a citação literal e conferi-la por substring transforma "confie em mim" em "confira você": ou a prova está no edital, ou o valor não entra no parecer.

**O que custa:** um modelo que parafraseia o trecho (em vez de copiar) perde campos que acertou, e o extrator por regras precisa carregar o trecho junto de cada valor. O rebaixamento também descarta valores possivelmente corretos; entre repetir uma pergunta ao órgão e assinar um parecer com origem inventada, repete-se a pergunta.

---

## A chamada à API está escrita e não foi executada

**A escolha:** `extrator_modelo.extrair()` faz a chamada real (SDK da Anthropic, modelo `claude-opus-5`), mas o desenvolvimento foi feito sem chave e a chamada não foi executada neste repositório. O que os testes exercitam é a fronteira de dentro: `texto_da_resposta()` (recusa, truncamento, resposta sem texto) e `interpretar_resposta()` (todo tipo de lixo estrutural), além da conferência comum.

**Por quê:** chave de API não entra em repositório nem em fluxo de desenvolvimento de portfólio, e fingir que a chamada foi testada seria pior do que declarar que não foi. A aposta técnica é que o risco mora quase todo do lado testável: a rede devolve bytes, e tudo que decide se esses bytes viram parecer está coberto por teste.

**O que custa:** a integração de ponta a ponta não tem garantia comprovada: um erro de parâmetro na chamada (nome de campo, formato do schema) só apareceria na primeira execução com chave. O custo é declarado no README em vez de escondido.

---

## Structured outputs e, mesmo assim, conferência local

**A escolha:** a chamada pede a resposta com `output_config.format` (JSON schema), e `interpretar_resposta()` valida tudo de novo localmente: formato, status, tipos, trechos.

**Por quê:** o schema elimina uma classe de lixo (JSON malformado, campo faltando) na origem, e custa uma linha. Mas ele garante a forma, não o conteúdo: um valor que não bate com o trecho, um trecho que não existe no edital e um status trocado passam por qualquer schema. Além disso, código que não foi executado não tem garantia comprovada; a validação local precisa sustentar o parecer sozinha.

**O que custa:** validação em dois lugares parece redundância. Não é: uma valida forma no servidor, a outra valida verdade no cliente, e só a segunda é testável sem chave.

---

## Editais fictícios pela estrutura da Lei 14.133/2021

**A escolha:** os três editais são inventados, com órgãos fictícios (Serra do Lume e Porto do Mangal não existem), mas seguem a estrutura, as seções e as fórmulas que a Lei 14.133/2021 induz em editais reais, inclusive os tetos de garantia (art. 58, § 1º; arts. 96 a 99). Dois trazem defeitos plantados com gabarito: um valor de garantia que não corresponde ao percentual e uma data de sessão que não existe no calendário.

**Por quê:** edital real traria nome de órgão e de servidores públicos reais para um repositório que planta defeitos de propósito, e associar erro fabricado a instituição existente é afirmação falsa sobre terceiros. A lei, por outro lado, é pública: a estrutura que o extrator explora é a da lei, não a de um documento particular. E os defeitos plantados vêm do mesmo princípio dos projetos anteriores da trilha: erro de digitação humana em documento oficial, do tipo que já apareceu em auditoria real.

**O que custa:** três editais escritos para seguir o padrão não provam robustez contra a variedade do mundo real (formatação de PDF, OCR, seções renumeradas). O projeto declara isso como limitação em vez de fingir cobertura.

---

## O valor extraído é texto bruto; quem interpreta é a conferência

**A escolha:** os extratores devolvem o valor como aparece no edital (`"R$ 4.280.000,00"`, `"5%"`, `"31/06/2026"`), e a interpretação (Decimal, data, inteiro) acontece uma vez só, em `contrato.converter()`, dentro da conferência.

**Por quê:** se cada extrator normalizasse do seu jeito, o mesmo edital poderia produzir pareceres diferentes por diferença de parsing, e um erro de interpretação ficaria espalhado em dois lugares. Com o bruto no contrato, a data impossível `31/06/2026` chega inteira à conferência e vira achado com a citação exata, em vez de virar exceção dentro de um extrator.

**O que custa:** o contrato carrega strings onde um tipo forte seria mais confortável, e todo consumidor do JSON precisa saber que `valor` é texto. É o preço de ter um único ponto de interpretação, testável e com mensagens de erro que citam o que estava escrito.

---

## A conferência cruzada usa o valor estimado como base

**A escolha:** o cruzamento entre percentual e valor absoluto da garantia usa o valor estimado da contratação como base, com tolerância de R$ 0,01.

**Por quê:** o valor exato do contrato só existe depois da adjudicação; na fase de edital, o próprio órgão calcula o valor de referência da garantia sobre o valor estimado. É a conta que o edital fez, então é a conta que se confere.

**O que custa:** num edital que calcule a garantia sobre outra base (lote, item, valor anual), a conferência acusaria divergência falsa. A tolerância apertada é deliberada: melhor um alerta a mais, com a conta exposta no parecer, do que uma divergência de milhares de reais passando como arredondamento.

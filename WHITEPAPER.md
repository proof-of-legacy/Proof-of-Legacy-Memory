# PoLM — Proof of Legacy Memory
## Whitepaper Oficial v1.0

**Fundador:** Aluisio Fernandes "Aluminium"  
**Data:** 2025  
**Website:** polm.io (em breve)  
**Repositório:** github.com/proof-of-legacy  

---

## Resumo Executivo

PoLM (Proof of Legacy Memory) é uma blockchain descentralizada com um mecanismo de consenso único no mundo: **Prova de Latência de RAM**. Diferente do Bitcoin (que favorece quem tem mais hardware novo e caro) ou do Ethereum (que favorece quem tem mais dinheiro), o PoLM inverte a lógica — **hardware mais antigo minera mais**.

O PoLM não é apenas uma criptomoeda. É uma **infraestrutura global de registro de propriedade e identidade**, onde qualquer bem físico, digital ou jurídico pode ser registrado de forma imutável, verificável e permanente — sem depender de cartório, governo ou empresa centralizada.

---

## 1. O Problema

O mundo moderno tem três grandes falhas em registro de propriedade:

**1.1 Centralização**  
Registros de imóveis, contratos, patentes e identidades dependem de instituições centralizadas (cartórios, governos, bancos). Uma falha, corrupção ou desastre pode apagar ou falsificar registros.

**1.2 Exclusão Digital**  
Blockchain atual (Bitcoin, Ethereum) exige hardware novo e caro para participar. Bilhões de computadores antigos são descartados todo ano, gerando lixo eletrônico, mesmo quando ainda funcionam perfeitamente.

**1.3 Barreiras de Acesso**  
Registrar uma propriedade em cartório custa caro, é lento e só funciona dentro de fronteiras nacionais. Não existe um registro universal de propriedade acessível a qualquer pessoa no mundo.

---

## 2. A Solução PoLM

### 2.1 Proof of Legacy Memory (Prova de Memória Legada)

O PoLM usa a **latência da RAM** como prova de trabalho. RAM mais antiga (DDR2, DDR3) tem latência maior — e isso se torna uma **vantagem de mineração**:

| Tipo de RAM | Multiplicador | Exemplo de hardware |
|-------------|--------------|---------------------|
| DDR2        | 2.5x         | PCs de 2004-2009    |
| DDR3        | 1.8x         | PCs de 2007-2014    |
| DDR4        | 1.0x         | PCs de 2014-2020    |
| DDR5        | 0.6x         | PCs de 2021+        |

Um computador com DDR2 de 2005 minera **2.5x mais** que um PC novo com DDR5. Isso é revolucionário.

### 2.2 Proteção Anti-Trapaça

O PoLM usa múltiplas camadas de segurança para garantir que apenas hardware físico real possa minerar:

- **Detecção de VM** — VMware, VirtualBox, QEMU, WSL, Docker, KVM e outros são detectados e bloqueados
- **Fingerprint de Hardware** — cada prova é vinculada ao hardware físico específico (motherboard, CPU, RAM slots)
- **Validação de Latência** — a latência medida é comparada com o esperado para o tipo de RAM declarado. Quem declara DDR2 mas tem DDR4 é penalizado
- **Seed derivado do bloco** — impossível reutilizar provas antigas (anti-replay)

### 2.3 Registro Universal de Propriedade

Qualquer pessoa pode registrar na blockchain PoLM:

**Bens Físicos:**
- Imóveis (casas, terrenos, apartamentos)
- Veículos (carros, motos, caminhões)
- Máquinas e equipamentos industriais
- Obras de arte e colecionáveis

**Bens Empresariais:**
- Contratos digitais
- Participação societária
- Patentes e marcas
- Licenças e concessões

**Bens Digitais:**
- Documentos e certificados
- Direitos autorais
- Código-fonte e projetos tecnológicos
- Identidade digital

Cada registro é:
- **Imutável** — não pode ser alterado após confirmação
- **Verificável** — qualquer pessoa pode verificar em qualquer lugar do mundo
- **Permanente** — existe enquanto a rede existir
- **Barato** — taxa de registro em PoLM, sem intermediários

---

## 3. Tokenomics

| Parâmetro | Valor |
|-----------|-------|
| Supply máximo | 32.000.000 PoLM |
| Recompensa inicial | 50 PoLM/bloco |
| Halving | A cada 210.000 blocos |
| Tempo alvo | 60 segundos/bloco |
| Símbolo | POLM |
| Decimais | 8 (como Bitcoin) |
| Unidade mínima | 1 satoshi = 0.00000001 POLM |

### Distribuição estimada:
- Mineradores (hardware legado): ~95%
- Fundador (blocos genesis + primeiros blocos): ~5%

---

## 4. Casos de Uso

### 4.1 Para Governos
Prefeituras e governos estaduais podem usar a rede PoLM como camada de registro imutável para:
- Registro de imóveis e terrenos
- Certidões de nascimento e óbito
- Contratos públicos e licitações
- Diplomas e certificados educacionais

### 4.2 Para Empresas
- Registro de patentes e propriedade intelectual
- Contratos inteligentes entre empresas
- Rastreabilidade de cadeia de suprimentos
- Certificação de autenticidade de produtos

### 4.3 Para Pessoas Físicas
- Compra e venda de imóveis sem cartório
- Registro de obras artísticas e musicais
- Testamentos e heranças digitais
- Identidade digital universal

### 4.4 Para Mineradores
- Dar utilidade a computadores antigos
- Gerar renda com hardware considerado obsoleto
- Participar de uma rede global descentralizada

---

## 5. Arquitetura Técnica

### 5.1 Consenso
- Algoritmo: Proof of Legacy Memory (PoLM)
- Dificuldade: ajuste automático a cada 144 blocos
- Proteção contra reorganização: máximo 100 blocos
- Anti-VM: detecção em múltiplas camadas

### 5.2 Transações
- Modelo UTXO (como Bitcoin)
- Assinatura ECDSA secp256k1
- Anti replay-attack via CHAIN_ID
- Maturação de coinbase: 100 blocos

### 5.3 Rede
- Protocolo P2P proprietário
- Porta padrão: 5555
- Máximo de peers: 125
- Versão do protocolo: PoLM/1.1

### 5.4 Registro de Ativos (em desenvolvimento)
- Transações especiais tipo ASSET_REGISTER
- Hash do documento + metadados na blockchain
- NFT nativo para bens únicos
- API REST para integração com sistemas externos

---

## 6. Roadmap

### Fase 1 — Mainnet (2025) ✅ Concluído
- [x] Blockchain funcional
- [x] Mineração por latência de RAM
- [x] Rede P2P com 2+ nós
- [x] Transferências funcionais
- [x] Explorer web

### Fase 2 — Segurança (2025) 🔄 Em andamento
- [x] Detecção de VM
- [x] Fingerprint de hardware
- [ ] Validação ECDSA completa
- [ ] Auditoria de segurança

### Fase 3 — Registro de Ativos (2026)
- [ ] Transações ASSET_REGISTER
- [ ] Interface web de registro
- [ ] API para integração governamental
- [ ] NFTs nativos

### Fase 4 — Ecossistema (2026)
- [ ] Listagem em exchanges
- [ ] Aplicativo móvel
- [ ] SDK para desenvolvedores
- [ ] Parceria com prefeituras piloto

---

## 7. Propriedade Intelectual e Licença

PoLM é um projeto proprietário criado e de propriedade de **Aluisio Fernandes "Aluminium"**.

O código-fonte é distribuído sob licença **PoLM Proprietary License v1.0**, que permite:
- ✅ Uso pessoal para mineração
- ✅ Estudo do código
- ✅ Contribuições via pull request aprovado

E proíbe:
- ❌ Cópia do projeto sob outro nome
- ❌ Modificação do algoritmo de consenso
- ❌ Uso comercial sem autorização do fundador
- ❌ Criação de forks sem aprovação

**"PoLM", "Proof of Legacy Memory" e "Aluminium"** são marcas do fundador.

---

## 8. Sobre o Fundador

**Aluisio Fernandes**, conhecido como **"Aluminium"**, é o criador e fundador da rede PoLM. A ideia nasceu da observação de que hardware antigo ainda tem valor real — e que o mundo precisa de uma infraestrutura de registro de propriedade que seja verdadeiramente descentralizada, acessível e permanente.

*"Hardware antigo não morre, ele minera. DDR2 tem valor. Cada ciclo de RAM é prova de vida."*  
— Aluisio Fernandes "Aluminium", mensagem do bloco genesis PoLM

---

## Contato

- GitHub: github.com/proof-of-legacy
- Website: polm.io (em breve)
- Email: aluminium@polm.io (em breve)

---

*© 2025 Aluisio Fernandes "Aluminium". Todos os direitos reservados.*

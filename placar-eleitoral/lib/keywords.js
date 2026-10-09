// Palavras e expressões associadas a cada candidato.
// Tudo é comparado depois da normalização (minúsculas, sem acentos, sem # e @),
// então escreva os termos sem acento. Edite à vontade para ajustar a contagem.

export const CANDIDATOS = {
  lula: {
    nome: "Lula",
    nomeCompleto: "Luiz Inácio Lula da Silva",
    partido: "PT",
    numero: "13",
  },
  flavio: {
    nome: "Flávio Bolsonaro",
    nomeCompleto: "Flávio Nantes Bolsonaro",
    partido: "PL",
    numero: "22",
  },
};

// Termos que contam como voto direto.
export const TERMOS = {
  lula: [
    "13", "lula", "lulinha", "lulao", "lula la", "lulala", "lula 13", "lula13",
    "luiz inacio", "lula da silva", "pt", "petista", "petistas", "lulista", "lulistas",
    "partido dos trabalhadores", "faz o l", "fazoele", "faz o ele", "time lula",
    "vote 13", "voto 13", "e 13", "eh 13", "fecha com lula", "lula presidente",
    "lula de novo", "lula 4", "lula2026", "estrela vermelha",
  ],
  flavio: [
    "22", "flavio", "flavinho", "flavio bolsonaro", "bolsonaro", "bolsonarista",
    "bolsonaristas", "bolso", "mito", "o mito", "pl", "partido liberal", "zero um",
    "01", "b22", "vote 22", "voto 22", "e 22", "eh 22", "time bolsonaro",
    "fecha com flavio", "flavio presidente", "bolsonaro 2026", "flavio2026",
    "familia bolsonaro", "patriota", "patriotas", "direita",
  ],
};

// Expressões de rejeição: "fora Lula" não é voto para o Lula.
// Elas são removidas do texto antes da contagem e contam para o adversário.
export const REJEICAO = {
  // rejeita o Lula => voto para o Flávio
  lula: [
    "fora lula", "fora pt", "lula nunca mais", "nunca lula", "anti lula", "antilula",
    "antipetista", "antipetismo", "lula ladrao", "lula na cadeia", "lula preso",
    "lula nao", "pt nunca mais", "nunca mais pt", "faz o l nao",
  ],
  // rejeita o Flávio/Bolsonaro => voto para o Lula
  flavio: [
    "fora bolsonaro", "fora flavio", "fora pl", "bolsonaro nunca mais", "nunca bolsonaro",
    "anti bolsonaro", "antibolsonaro", "antibolsonarista", "ele nao", "elenao",
    "bolsonaro na cadeia", "bolsonaro preso", "flavio nao", "bolsonaro nao",
    "sem anistia", "fora mito",
  ],
};

// Emojis/sinais que costumam acompanhar cada lado (peso igual a um termo).
export const EMOJIS = {
  lula: ["🚩", "⭐", "🌟"],
  flavio: ["🇧🇷", "💚💛", "💛💚"],
};

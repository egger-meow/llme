// Shared children and claim IDs are references. Keep trial assumptions separate from evidence.
const REVIEW_CASES = {
  p46: {
    name: "P46 的都市分區訪談",
    tab: "P46 · 都市分區",
    type: "真人訪談",
    intro: "提高開發密度後，交通會更塞嗎？P46 先說通常會，再補上他會改判的條件。",
    root: "person",
    initial: "transit",
    nodes: {
      person: {
        label: "P46 的所有情況", kind: "本人", children: ["healthcare", "surveillance", "zoning"], claims: [],
        about: "從三個議題進入同一個人的訪談。本例只取都市分區的一段話，根節點暫無跨議題主張。"
      },
      healthcare: {
        label: "醫療", kind: "議題", children: [], claims: [],
        about: "HugAgent 的醫療議題入口。本頁選取的證據只談都市交通。"
      },
      surveillance: {
        label: "公共監控", kind: "議題", children: [], claims: [],
        about: "HugAgent 的公共監控議題入口。本頁選取的證據只談都市交通。"
      },
      zoning: {
        label: "都市分區", kind: "議題", children: ["density"], claims: [],
        about: "訪談問到都市開發密度對交通的影響。選「提高開發密度」可讀 P46 在這個情境的判斷。"
      },
      density: {
        label: "提高開發密度", kind: "局部情境", children: ["transit"], claims: ["R1"], focus: "R1",
        about: "P46 預期提高密度後，交通多半會更塞。他還說出一種會改變這項預期的情況。"
      },
      transit: {
        label: "大眾運輸好搭且便宜", kind: "局部情境", children: [], claims: ["R2", "R3", "R1"], focus: "R2",
        about: "在提高開發密度的前提下，大眾運輸更容易搭，而且便宜。兩項都成立時，P46 對交通的預期改為持平。"
      }
    },
    claims: {
      R1: {
        from: "提高開發密度", relation: "多半使", to: "交通更壅塞",
        text: "P46 預期，提高開發密度通常會讓一般人遇到更多塞車。",
        kind: "因果預期", source: "e005"
      },
      R2: {
        from: "提高開發密度", relation: "在此條件下", to: "交通持平",
        text: "若大眾運輸更容易搭而且便宜，P46 預期提高密度後，交通壅塞程度會維持原狀。",
        kind: "因果預期", source: "e005"
      },
      R3: {
        from: "大眾運輸好搭且便宜", relation: "會使", to: "更多人改搭",
        text: "P46 認為更多人會改搭大眾運輸，並用這點解釋為什麼交通會持平。",
        kind: "本人給的理由", source: "e005", reasonFor: "R2"
      }
    },
    exceptions: [{local: "R2", base: "R1", condition: "transit"}],
    sources: {
      e005: {
        label: "P46 · 都市分區 · 訪談第 5 段",
        note: "三條主張都是這一段回答的中文轉述。此段是 Task 2 第 0311 題允許模型閱讀的訪談。",
        href: "../../ref/HugAgent/index.html#item=belief_dynamics_update-zoning-0311&qa=5",
        linkText: "讀訪談原文"
      }
    },
    trials: [
      {
        label: "好搭，而且便宜", conditions: ["density", "transit"],
        result: "交通持平", explanation: "兩項條件都成立。R2 取代 R1，R3 補上 P46 的理由。",
        active: ["R2", "R3"], overridden: ["R1"]
      },
      {
        label: "便宜，但明確沒有更好搭", conditions: ["density"],
        result: "交通多半更塞", explanation: "已知搭乘便利性沒有改善。兩項條件少了一項，沿用 R1。",
        active: ["R1"]
      },
      {
        label: "只知道便宜", conditions: ["density"],
        result: "暫估多半更塞", explanation: "還要知道搭乘有沒有變容易，才能決定 R2 是否取代 R1。",
        active: [], provisional: ["R1"], pending: ["R2"]
      },
      {
        label: "改問 P46 支持提高密度嗎？", conditions: ["density"],
        result: "這段話無法判定他的立場", explanation: "三條主張記錄他預期的交通變化與理由。要判定他的支持度，還需要談他本人政策立場的證據。",
        active: []
      }
    ]
  },
  roles: {
    name: "同一個人的不同身分",
    tab: "角色 · 工廠與家庭",
    type: "假設案例",
    intro: "同一個人可以是爸爸，也是工廠管理員。用兩個角色檢查條件交疊時，哪些判斷會一起生效。",
    root: "person",
    initial: "production",
    nodes: {
      person: {
        label: "這個人的所有情況", kind: "本人", children: ["father", "factory", "surveillance"], claims: [],
        about: "當爸爸和當工廠管理員是兩個角色。公共監控是議題，也能用來找到他以爸爸身分談校園攝影機的那項看法。"
      },
      father: {
        label: "當爸爸", kind: "角色", children: ["school"], claims: [],
        about: "從角色找到「以爸爸身分談校園攝影機」。假設案例只把下方的看法放在該情境。"
      },
      factory: {
        label: "當工廠管理員", kind: "角色", children: ["production"], claims: [],
        about: "這個角色在接單時要做增產決定。進入「工廠接單」可查看一般做法與局部條件。"
      },
      surveillance: {
        label: "公共監控", kind: "議題", children: ["school"], claims: [],
        about: "從議題也能讀到同一個校園攝影機節點與主張。"
      },
      school: {
        label: "以爸爸身分談校園攝影機", kind: "局部情境", children: [], claims: ["C1"], focus: "C1",
        about: "「當爸爸」和「公共監控」都通往這裡。兩條路共用同一條主張 C1。"
      },
      production: {
        label: "工廠接單", kind: "局部情境", children: ["injury", "night"], claims: ["F1"], focus: "F1",
        about: "假設這位管理員接單時通常願意增產。永久傷害風險會改變產量決定，夜班則有另一項巡檢安排。"
      },
      injury: {
        label: "可能造成永久傷害", kind: "局部情境", children: [], claims: ["F2", "F1"], focus: "F2",
        about: "工廠接單時若可能造成永久傷害，管理員會維持產量。這個條件改寫「通常願意增產」。"
      },
      night: {
        label: "夜班", kind: "局部情境", children: [], claims: ["F3", "F1"], focus: "F3",
        about: "夜班多一次巡檢。若也要決定本次產量，仍需檢查是否可能造成永久傷害。"
      }
    },
    claims: {
      F1: {
        from: "一般接單", relation: "通常願意", to: "增產",
        text: "假設這位管理員接到訂單時通常願意提高產量。",
        kind: "接單決定", source: "factoryExample"
      },
      F2: {
        from: "永久傷害風險", relation: "使他選擇", to: "維持產量",
        text: "假設他明說，若這張單可能讓人永久受傷，就維持產量。",
        kind: "接單決定", source: "factoryExample"
      },
      F3: {
        from: "夜班", relation: "加做", to: "一次巡檢",
        text: "假設管理員要求夜班多做一次巡檢。這項安排可以與增產或維持產量並存。",
        kind: "巡檢安排", source: "factoryExample"
      },
      C1: {
        from: "考慮校園攝影機", relation: "會關心", to: "誰能調閱影像",
        text: "在此假設中，他以爸爸身分談校園攝影機時，關心誰可以調閱影像。",
        kind: "在意的因素", source: "schoolExample"
      }
    },
    exceptions: [{local: "F2", base: "F1", condition: "injury"}],
    sources: {
      factoryExample: {
        label: "W7 工廠案例的假設延伸",
        note: "W7 提供選擇產量的背景。這裡設定一般接單、永久傷害例外和夜班巡檢三項條件，供研究者檢查設計。",
        href: "../../meetings/W7.pdf#page=7", linkText: "查看 W7 工廠案例"
      },
      schoolExample: {
        label: "為說明角色與議題交叉而設的例子",
        note: "C1 是本頁設定的假設看法，供檢查兩個入口能否指到同一條主張。"
      }
    },
    trials: [
      {
        label: "夜班，風險未知", conditions: ["production", "night"],
        result: "加做巡檢，增產暫定", explanation: "夜班足以決定巡檢安排。是否維持產量，還要確認這張單有沒有永久傷害風險。",
        active: ["F3"], provisional: ["F1"], pending: ["F2"]
      },
      {
        label: "夜班，可能永久傷人", conditions: ["production", "night", "injury"],
        result: "維持產量，並加做巡檢", explanation: "F2 取代一般的增產決定。夜班的 F3 同時成立，仍要多做一次巡檢。",
        active: ["F2", "F3"], overridden: ["F1"]
      },
      {
        label: "夜班，已排除永久傷害", conditions: ["production", "night"],
        result: "通常願意增產，並加做巡檢", explanation: "已確認永久傷害條件不成立。一般的增產決定與夜班巡檢安排可以同時沿用。",
        active: ["F1", "F3"]
      }
    ]
  }
};

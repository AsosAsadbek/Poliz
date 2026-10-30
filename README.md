# POLIZ Kalkulyatori

Arifmetik ifodani **POLIZ** (teskari polyak yozuvi, RPN) ko'rinishiga o'tkazadigan va
stek yordamida hisoblaydigan o'quv kalkulyatori. Hisoblashning har bir qadamini ko'rsatadi.

![Yorug' mavzu](docs/ekran-yorug.png)
![Tungi mavzu](docs/ekran-tungi.png)

## Ishga tushirish

Python 3.8+ kerak, tashqi kutubxonalar talab qilinmaydi (Tkinter Python bilan birga keladi).

```bash
python poliz_kalkulyator.py
```

Testlar:

```bash
python -m unittest -v
```

## Imkoniyatlar

- **Jonli natija.** Yozish davomida natija avtomatik chiqadi. Xato haqidagi xabar faqat
  Enter yoki «Hisoblash» bosilganda ko'rsatiladi, shuning uchun foydalanuvchi hali yozib
  turganida ekran qizarib ketmaydi.
- **Aniq xato xabarlari.** Xato qaysi belgida ekani aytiladi va o'sha belgi ifodada qizil
  rang bilan belgilanadi. Masalan: «Nolga bo'lish mumkin emas (3-belgi)», «Qavs yopilmagan»,
  «2 va ( orasida amal belgisi yo'q».
- **POLIZ ga o'tkazish qadamlari.** Deykstraning «saralash stansiyasi» algoritmi jadval
  ko'rinishida beriladi: token, bajarilgan amal, stek va chiqish.
- **Hisoblash qadamlari.** POLIZ stek yordamida qanday hisoblanishi bosqichma-bosqich
  ko'rsatiladi.
- **Ifoda daraxti.** Ifodaning grafik ko'rinishi.
- **Qadamni ifodada ko'rsatish.** Jadvaldagi qatorni tanlasangiz, unga mos belgi kiritish
  maydonida ajratib ko'rsatiladi.
- **Tarix.** Hisoblangan ifodalar `~/.poliz_tarix.json` fayliga saqlanadi. Ularni ↑/↓
  tugmalari bilan yoki «Tarix» bo'limida ikki marta bosib qayta yuklash mumkin.
- **Ekran klaviaturasi va tayyor namunalar.** «Namunalar ▾» menyusida tayyor ifodalar bor.
- **Yorug' va tungi mavzu** (Ctrl+T), shuningdek POLIZ, natijani nusxalash va ichki qo'llanma (F1).

## Qo'llab-quvvatlanadigan yozuv

| Belgi | Amal | Ustuvorlik |
|---|---|---|
| `^` (yoki `**`) | darajaga ko'tarish, o'ngdan assotsiativ: `2^3^2 = 2^9` | 4 |
| `~` | unar minus: `-(3+4)` → `3 4 + ~` | 3 |
| `*` `/` (yoki `×` `÷`) | ko'paytirish, bo'lish | 2 |
| `+` `-` | qo'shish, ayirish | 1 |

Kasr sonlarni `3.5` yoki `3,5` ko'rinishida yozish mumkin. Qavs sifatida `( )`, `[ ]` va
`{ }` ishlatiladi. Songa to'g'ridan-to'g'ri qo'yilgan minus manfiy son sifatida yoziladi:
`(3 + 4) * 2-(- 5)` → `3 4 + 2 * -5 -` → **19**. Ammo `-2^2 = -(2^2) = -4`, chunki daraja
unar minusdan oldin bajariladi.

## Klaviatura

| Tugma | Vazifasi |
|---|---|
| Enter | hisoblash |
| Esc | tozalash |
| ↑ / ↓ | tarixdagi ifodalar |
| Ctrl+Shift+C | natijani nusxalash |
| Ctrl+T | yorug' / tungi mavzu |
| F1 | qo'llanma |

## Tuzilishi

| Fayl | Vazifasi |
|---|---|
| `poliz_kalkulyator.py` | ishga tushirish fayli |
| `poliz.py` | mantiq: tokenlar, Shunting-yard, POLIZ ni hisoblash, daraxt (interfeysga bog'liq emas) |
| `gui.py` | Tkinter interfeysi |
| `test_poliz.py` | testlar |

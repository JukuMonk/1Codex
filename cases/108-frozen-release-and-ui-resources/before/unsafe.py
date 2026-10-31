# WRONG: исходники могут измениться между проверкой и выпуском.
def release(live, lint, load, export):
    lint(live)
    load(live)
    export('latest.cf')  # публикация до сверки; нет защиты старого результата

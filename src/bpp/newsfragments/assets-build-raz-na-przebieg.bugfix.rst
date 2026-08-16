Assety frontendu (CSS i tłumaczenia) budują się raz na przebieg testów,
a nie osobno w każdym procesie roboczym ``pytest-xdist``. Przy
``-n auto`` na dziesięciu rdzeniach startowało jedenaście równoległych
``grunt build`` piszących do tych samych plików — niepotrzebne obciążenie
maszyny i wyścig na zapisie.

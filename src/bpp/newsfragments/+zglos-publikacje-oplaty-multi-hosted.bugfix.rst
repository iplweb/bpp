Wizard zgłaszania publikacji nie crashuje już na kroku opłat w instalacji
multi-hosted: formularz kosztu publikacji przekazuje teraz uczelnię z requestu
do walidacji modelu, zamiast zgadywać przez ``Uczelnia.objects.get()``
(``MultipleObjectsReturned`` przy więcej niż jednej uczelni; Rollbar #400).

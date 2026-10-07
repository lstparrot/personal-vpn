# Oracle Cloud Always Free: подготовка VPS

Проверено по документации Oracle 7 октября 2026 года. Этот документ описывает создание аккаунта и VPS. **Текущий Ansible playbook пока не готов к запуску на стандартном образе OCI:** он заменяет системный firewall, а OCI требует сохранять правила доступа к служебным iSCSI адресам `169.254.0.2:3260` и `169.254.2.0/24:3260`. До отдельной реализации и проверки на OCI не запускайте `vpnctl.py deploy` на такой машине.

## Выбор

- Бесплатный вариант: один `VM.Standard.A1.Flex` с **1 OCPU и 4 GB RAM**, Ubuntu 24.04 LTS aarch64, загрузочный диск 50 GB, публичный IPv4. Убедитесь, что в консоли образ и shape отмечены **Always Free Eligible**. Лимит Always Free для всех A1-инстансов аккаунта вместе — 2 OCPU и 12 GB RAM. Ubuntu 24.04 и WireGuard доступны на Arm.
- Запасной вариант, если A1 недоступен: `VM.Standard.E2.1.Micro` с Ubuntu 24.04. У него 1 GB RAM и ограничение публичной полосы до 50 Mbps; сначала измерьте скорость и устойчивость.
- Oracle указывает **10 TB исходящего трафика в месяц** в Always Free. Это лимит на выход из OCI, а не обещание скорости или качества IP.

## Регистрация

1. Откройте [официальную регистрацию](https://signup.oraclecloud.com/). Укажите реальные данные, подтвердите email и телефон.
2. Выберите **US East (Ashburn)** как Home Region, если он доступен и подходит по задержке. Home Region после регистрации изменить нельзя; Always Free VM можно создать только в нём. Другие коммерческие регионы США допустимы, если доступны при регистрации.
3. Добавьте карту для проверки личности. Oracle не принимает виртуальные, одноразовые и prepaid карты; возможна временная авторизация небольшой суммы. Сама карта не даёт согласия на переход в платный аккаунт.
4. Завершите Free Trial. Не выбирайте платное обновление аккаунта или ресурсы без пометки Always Free Eligible. После окончания 30-дневного trial бесплатные ресурсы остаются, но платные trial-ресурсы удаляются.

## Создание VM

1. В консоли создайте compartment для проекта. Через **Networking → Virtual Cloud Networks → Start VCN Wizard → Create VCN with Internet Connectivity** создайте VCN и публичную подсеть.
2. Откройте **Compute → Instances → Create Instance**. Выберите созданный compartment, Ubuntu 24.04 LTS, shape `VM.Standard.A1.Flex`, 1 OCPU, 4 GB RAM и загрузочный том 50 GB. Проверьте пометку Always Free Eligible у выбранных ресурсов.
3. Выберите созданную VCN и **public subnet**; включите **Assign a public IPv4 address**. Добавьте **свой SSH public key**. Закрытый ключ храните только на своём компьютере; не загружайте его в репозиторий или чат.
4. В Security List публичной подсети добавьте **stateful ingress** `UDP`, destination port `51820`, source `0.0.0.0/0`. Сохраните правило `TCP 22` для SSH, по возможности ограничив source своим текущим публичным IP. Egress оставьте разрешённым для первого теста. DNS-порт 53 наружу не открывайте.
5. Дождитесь статуса Running, запишите public IPv4 и проверьте вход `ssh ubuntu@<public-ip>` с той машины, где лежит закрытый SSH-ключ. Затем проверьте `sudo -n true` и доступ к консоли восстановления.
6. До установки VPN проверьте, что VM не лишилась сети после перезагрузки. После адаптации firewall проекта потребуется повторить тесты из `VERIFY.md`.

Если создание A1 возвращает **Out of host capacity**, Oracle советует попробовать другой availability domain в той же Home Region или подождать. Переход на платный аккаунт для этого проекта не требуется. Oracle может забирать простаивающие Always Free VM; храните исходники и клиентские ключи в отдельной защищённой резервной копии.

## Источники

- [Oracle: регистрация Free Tier](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm)
- [Oracle: Always Free лимиты, исходящий трафик и отзыв простаивающих VM](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle: создание первой Linux VM](https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm)
- [Oracle: обязательные правила firewall для системного диска](https://docs.oracle.com/en-us/iaas/Content/Compute/References/images.htm)
- [Oracle: Security Lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/creating-securitylist.htm)

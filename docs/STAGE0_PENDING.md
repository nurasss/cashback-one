# Stage 0 Discovery Requirements (POSCENTER ONE / 1C Metadata)

Stage 0 pilot investigation on a real POSCENTER ONE database must determine and verify the following concrete 1C metadata objects before final mapping:

1. **Card catalog:** The exact name of the 1C catalog storing loyalty/bonus cards (e.g., `Справочник.БонусныеКарты`, `Справочник.ИнформационныеКарты`, or register).
2. **Barcode field:** The attribute holding the 13-digit card barcode / code.
3. **Phone field:** The attribute or contact information table holding the customer phone number.
4. **Full name source:** The attribute or counterparty reference holding the customer's full name (`ФИО`).
5. **Blocked flag:** The boolean attribute or status indicating whether the card is blocked/disabled (`КартаЗапрещена` / `Заблокирована`).
6. **Balance source:** The exact accumulation register or field storing the current bonus balance (e.g., `РегистрНакопления.БонусныеБаллы.Остатки`).
7. **Bonus movement register:** The accumulation register or document journal recording accruals, redemptions, and adjustments.
8. **External transaction ID:** The unique transaction/movement identifier mapping to 1C recorder (`Регистратор` + line index or GUID).
9. **Receipt reference:** The receipt number or document identifier associated with the movement.
10. **Store reference:** The retail store / point of sale reference for the transaction.
11. **Updated/change timestamp:** The attribute, revision, or change-tracking mechanism used for incremental synchronization.

> **Note:** No assumptions or speculative 1C object names should be introduced into production code prior to the completion of Stage 0 on a live database copy.

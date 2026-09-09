import logging
import threading
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURAÇÃO
# ============================================================

# Intervalo do monitor.
CHECK_INTERVAL = 0.20

# Timeout APENAS das requisições HTTP usadas para verificar
# se a internet está funcionando.
#
# Não tem relação com Playwright.
PROBE_TIMEOUT = 0.50


# Quantidade de falhas consecutivas para disparar recuperação.
FAILURES_TO_TRIGGER = 2


# Quantidade de sucessos consecutivos para considerar
# definitivamente que a internet voltou.
SUCCESSES_TO_RECOVER = 3


# Tempo entre tentativas do Playwright.
TRIGGER_RETRY_DELAY = 0.5


# ============================================================
# PORTAL
# ============================================================

PORTAL_URL = "http://10.125.128.1/status"

SUCCESS_URL = "**irmaosgoncalves.com.br**"


# ============================================================
# URLS DE TESTE DA INTERNET
# ============================================================

PROBE_URLS = [
    "http://example.com",
    "http://neverssl.com",
]


# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("internet-monitor")


# ============================================================
# HTTP REDIRECT HANDLER
# ============================================================

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """
    Impede o urllib de seguir redirecionamentos.

    Se houver captive portal/redirecionamento,
    consideramos que a internet ainda não está liberada.
    """

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl
    ):
        return None


# ============================================================
# TESTE INDIVIDUAL DE INTERNET
# ============================================================

def http_probe(url):
    """
    Testa uma URL.

    Retorna True somente se:
        HTTP 200

    Retorna False em:
        timeout
        DNS
        conexão recusada
        HTTP 3xx
        HTTP 4xx
        HTTP 5xx
        qualquer outro erro
    """

    try:

        opener = urllib.request.build_opener(
            NoRedirect
        )

        response = opener.open(
            url,
            timeout=PROBE_TIMEOUT
        )

        return response.status == 200

    except urllib.error.HTTPError:

        return False

    except Exception:

        return False


# ============================================================
# TESTE DE INTERNET
# ============================================================

def internet_is_up():
    """
    Testa as URLs simultaneamente.

    Basta UMA responder HTTP 200 para considerar
    a internet disponível.
    """

    with ThreadPoolExecutor(
        max_workers=len(PROBE_URLS)
    ) as executor:

        futures = [
            executor.submit(
                http_probe,
                url
            )
            for url in PROBE_URLS
        ]

        for future in futures:

            try:

                if future.result():

                    return True

            except Exception:

                pass

    return False


# ============================================================
# PLAYWRIGHT
# ============================================================

def run_trigger():
    """
    Executa a autenticação do portal.

    IMPORTANTE:

    Playwright NÃO possui timeout.

    Todas as operações podem esperar indefinidamente:

        goto
        check
        click
        wait_for_url

    O Playwright só termina quando:

        1. conseguir concluir
        2. ocorrer um erro real
        3. o processo for encerrado
    """

    playwright = None
    browser = None
    context = None
    page = None

    inicio = time.monotonic()

    try:

        # ====================================================
        # INICIA PLAYWRIGHT
        # ====================================================

        logger.info(
            "Iniciando Playwright"
        )

        playwright = sync_playwright().start()

        # ====================================================
        # INICIA CHROMIUM
        # ====================================================

        logger.info(
            "Iniciando Chromium"
        )

        browser = playwright.chromium.launch(
            headless=False,

            args=[
                # --------------------------------------------
                # REDUZ COISAS DESNECESSÁRIAS DO CHROMIUM
                # --------------------------------------------

                "--disable-background-networking",

                "--disable-background-timer-throttling",

                "--disable-breakpad",

                "--disable-component-update",

                "--disable-default-apps",

                "--disable-features=Translate,MediaRouter",

                "--disable-popup-blocking",

                "--disable-renderer-backgrounding",

                "--no-first-run",

                "--no-default-browser-check",
            ],
        )

        # ====================================================
        # CONTEXTO
        # ====================================================

        context = browser.new_context()

        # ====================================================
        # PÁGINA
        # ====================================================

        page = context.new_page()

        # ====================================================
        # SEM TIMEOUT
        # ====================================================

        page.set_default_timeout(0)

        page.set_default_navigation_timeout(0)

        # ====================================================
        # BLOQUEIO DE RECURSOS DESNECESSÁRIOS
        # ====================================================

        def handle_route(route):

            resource_type = route.request.resource_type

            if resource_type in (
                "image",
                "media",
                "font",
                "stylesheet",
            ):

                route.abort()

            else:

                route.continue_()

        page.route(
            "**/*",
            handle_route
        )

        # ====================================================
        # ACESSA PORTAL
        # ====================================================

        logger.info(
            "Acessando página inicial do portal"
        )

        page.goto(
            PORTAL_URL,
            wait_until="domcontentloaded",
        )

        # ====================================================
        # MARCA POLICY
        # ====================================================

        logger.info(
            "Marcando radio #policy"
        )

        page.check(
            "#policy"
        )

        # ====================================================
        # CLICA EM PRÓXIMO
        # ====================================================

        logger.info(
            "Clicando em 'Próximo'"
        )

        page.locator(
            'button:has-text("Próximo")'
        ).click()

        # ====================================================
        # AGUARDA REDIRECIONAMENTO
        # ====================================================

        logger.info(
            "Aguardando redirecionamento para "
            "irmaosgoncalves.com.br"
        )

        page.wait_for_url(
            SUCCESS_URL
        )

        # ====================================================
        # SUCESSO
        # ====================================================

        duracao = (
            time.monotonic() - inicio
        )

        logger.info(
            "Redirecionamento concluído com sucesso!"
        )

        logger.info(
            f"Tempo do Playwright: "
            f"{duracao:.3f}s"
        )

        return True

    # ========================================================
    # ERRO
    # ========================================================

    except Exception as e:

        duracao = (
            time.monotonic() - inicio
        )

        logger.error(
            f"Erro no Playwright após "
            f"{duracao:.3f}s: {e}"
        )

        return False

    # ========================================================
    # FECHAMENTO
    # ========================================================

    finally:

        # ----------------------------------------------------
        # FECHA PÁGINA
        # ----------------------------------------------------

        if page is not None:

            try:

                page.close()

            except Exception as e:

                logger.warning(
                    f"Erro ao fechar página: {e}"
                )

        # ----------------------------------------------------
        # FECHA CONTEXTO
        # ----------------------------------------------------

        if context is not None:

            try:

                context.close()

            except Exception as e:

                logger.warning(
                    f"Erro ao fechar contexto: {e}"
                )

        # ----------------------------------------------------
        # FECHA BROWSER
        # ----------------------------------------------------

        if browser is not None:

            try:

                logger.info(
                    "Encerrando browser"
                )

                browser.close()

            except Exception as e:

                logger.warning(
                    f"Erro ao fechar browser: {e}"
                )

        # ----------------------------------------------------
        # PARA PLAYWRIGHT
        # ----------------------------------------------------

        if playwright is not None:

            try:

                playwright.stop()

            except Exception as e:

                logger.warning(
                    f"Erro ao parar Playwright: {e}"
                )


# ============================================================
# CONTROLE DO GATILHO
# ============================================================

trigger_lock = threading.Lock()

trigger_running = False


# ============================================================
# EXECUTA GATILHO
# ============================================================

def execute_trigger():
    """
    Executa o Playwright em uma thread separada.

    Enquanto estiver executando:

        o monitor NÃO fica fazendo probes

    O próprio worker verifica a internet depois
    que o Playwright terminar.
    """

    global trigger_running

    # ========================================================
    # EVITA DUPLICAÇÃO
    # ========================================================

    with trigger_lock:

        if trigger_running:

            logger.warning(
                "Gatilho já está em execução."
            )

            return

        trigger_running = True

    # ========================================================
    # WORKER
    # ========================================================

    def worker():

        global trigger_running

        tentativa = 0

        try:

            while True:

                # ============================================
                # PRIMEIRO TESTA INTERNET
                # ============================================

                if internet_is_up():

                    logger.info(
                        "Internet já está funcionando. "
                        "Nenhuma nova tentativa necessária."
                    )

                    break

                # ============================================
                # NOVA TENTATIVA
                # ============================================

                tentativa += 1

                logger.warning(
                    "INTERNET FORA -> "
                    "DISPARANDO PLAYWRIGHT "
                    f"(tentativa {tentativa})"
                )

                inicio = time.monotonic()

                sucesso = run_trigger()

                duracao = (
                    time.monotonic() - inicio
                )

                # ============================================
                # PLAYWRIGHT SUCESSO
                # ============================================

                if sucesso:

                    logger.info(
                        "Playwright terminou com sucesso "
                        f"na tentativa {tentativa}."
                    )

                    logger.info(
                        f"Tempo total da tentativa: "
                        f"{duracao:.3f}s"
                    )

                    # ----------------------------------------
                    # CONFIRMA INTERNET
                    # ----------------------------------------

                    logger.info(
                        "Confirmando internet..."
                    )

                    if internet_is_up():

                        logger.info(
                            "Internet confirmada. "
                            "Gatilho encerrado."
                        )

                        break

                    # ----------------------------------------
                    # PORTAL TERMINOU MAS INTERNET AINDA NÃO
                    # ----------------------------------------

                    logger.warning(
                        "Playwright terminou, mas a internet "
                        "ainda está indisponível."
                    )

                # ============================================
                # PLAYWRIGHT FALHOU
                # ============================================

                else:

                    logger.error(
                        "Playwright falhou na tentativa "
                        f"{tentativa}."
                    )

                # ============================================
                # RETRY
                # ============================================

                logger.info(
                    f"Nova tentativa em "
                    f"{TRIGGER_RETRY_DELAY:.1f}s..."
                )

                time.sleep(
                    TRIGGER_RETRY_DELAY
                )

        except Exception as e:

            logger.exception(
                f"Erro no worker do gatilho: {e}"
            )

        finally:

            with trigger_lock:

                trigger_running = False

            logger.info(
                "Worker do gatilho encerrado."
            )

    # ========================================================
    # THREAD
    # ========================================================

    thread = threading.Thread(
        target=worker,
        daemon=True,
        name="playwright-trigger",
    )

    thread.start()


# ============================================================
# MONITOR PRINCIPAL
# ============================================================

def monitor():

    failures = 0
    successes = 0

    internet_down = False

    # ========================================================
    # CABEÇALHO
    # ========================================================

    logger.info(
        "=============================================="
    )

    logger.info(
        "Monitor de internet iniciado"
    )

    logger.info(
        "=============================================="
    )

    logger.info(
        f"Intervalo: "
        f"{CHECK_INTERVAL * 1000:.0f} ms"
    )

    logger.info(
        f"Timeout probe HTTP: "
        f"{PROBE_TIMEOUT * 1000:.0f} ms"
    )

    logger.info(
        f"Falhas para disparar: "
        f"{FAILURES_TO_TRIGGER}"
    )

    logger.info(
        f"Sucessos para recuperar: "
        f"{SUCCESSES_TO_RECOVER}"
    )

    logger.info(
        f"Intervalo entre tentativas Playwright: "
        f"{TRIGGER_RETRY_DELAY:.1f}s"
    )

    logger.info(
        "Playwright timeout: DESABILITADO"
    )

    logger.info(
        "=============================================="
    )

    # ========================================================
    # LOOP
    # ========================================================

    while True:

        start = time.monotonic()

        # ====================================================
        # VERIFICA SE O PLAYWRIGHT ESTÁ TRABALHANDO
        # ====================================================

        with trigger_lock:

            recovering = trigger_running

        # ====================================================
        # RECUPERAÇÃO EM ANDAMENTO
        # ====================================================

        if recovering:

            # -----------------------------------------------
            # NÃO FAZ HTTP PROBE AQUI
            # -----------------------------------------------

            # O worker do Playwright cuida da recuperação.

            time.sleep(
                CHECK_INTERVAL
            )

            continue

        # ====================================================
        # TESTA INTERNET
        # ====================================================

        up = internet_is_up()

        # ====================================================
        # INTERNET FUNCIONANDO
        # ====================================================

        if up:

            # -----------------------------------------------
            # ZERA FALHAS
            # -----------------------------------------------

            failures = 0

            successes += 1

            # -----------------------------------------------
            # CONFIRMA RECUPERAÇÃO
            # -----------------------------------------------

            if (
                internet_down
                and successes >= SUCCESSES_TO_RECOVER
            ):

                internet_down = False

                logger.info(
                    "Internet voltou. "
                    "Monitor rearmado."
                )

                successes = 0

        # ====================================================
        # INTERNET FORA
        # ====================================================

        else:

            successes = 0

            # -----------------------------------------------
            # SOMENTE CONTA ANTES DO GATILHO
            # -----------------------------------------------

            if not internet_down:

                failures += 1

                # -------------------------------------------
                # LOG
                # -------------------------------------------

                logger.warning(
                    "Falha de conexão "
                    f"{failures}/{FAILURES_TO_TRIGGER}"
                )

                # -------------------------------------------
                # DISPARA PLAYWRIGHT
                # -------------------------------------------

                if failures >= FAILURES_TO_TRIGGER:

                    internet_down = True

                    failures = 0

                    logger.warning(
                        "=========================================="
                    )

                    logger.warning(
                        "INTERNET CAIU!"
                    )

                    logger.warning(
                        "Iniciando recuperação via Playwright."
                    )

                    logger.warning(
                        "=========================================="
                    )

                    execute_trigger()

        # ====================================================
        # MANTÉM INTERVALO
        # ====================================================

        elapsed = (
            time.monotonic() - start
        )

        sleep_time = (
            CHECK_INTERVAL - elapsed
        )

        if sleep_time > 0:

            time.sleep(
                sleep_time
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        monitor()

    except KeyboardInterrupt:

        logger.info(
            "Monitor encerrado pelo usuário."
        )

    except Exception as e:

        logger.exception(
            f"Erro fatal no monitor: {e}"
        )
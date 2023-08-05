import requests
import random


class NodeIP:
    def __init__(
        self,
        logger,
        force_fake_ip: bool = False,
        save_path: str = None,
    ) -> None:
        self.logger = logger
        self.force_fake_ip = force_fake_ip
        self.save_path = save_path

    def _random_num_1_255(self):
        rand_str = str(random.randint(1, 255))
        return rand_str

    def _get_ip(self):
        res = requests.get("https://www.cloudflare.com/cdn-cgi/trace/")

        res_status = res.status_code
        if res_status == 200:
            res_text = res.text.splitlines()[2].split("=")[1]
        else:
            res_text = None

        return res_text, res_status

    def _save_ip_as_text(self, pre_message: str, ip: str):
        if self.save_path is None:
            pass
        else:
            with open(f"{self.save_path}/server_ip.txt", "w", encoding="utf-8") as f:
                f.write(f"{pre_message} {ip}")

    def get_fake_ip(self):
        random_ip = self._random_num_1_255()
        for _ in range(3):
            random_ip += f".{self._random_num_1_255()}"

        self.logger.warning(f"Using a random Fake IP as node ID! ({random_ip})")
        self.logger.warning(
            f"This 'Fake IP' will change for every restart of the node script!"
        )
        self._save_ip_as_text("Fake IP = ", random_ip)
        return random_ip

    def get_node_ip(self, maximum_tries: int):
        if self.force_fake_ip:
            self.logger.info(f"Forcing Fake IP: Skipping getting node ip !!")
            return self.get_fake_ip()
        else:
            for _ in range(maximum_tries):
                res = self._get_ip()
                res_ip = res[0]
                if res_ip is not None:
                    self.logger.info(f"Node Ip detected  ({res_ip}).")
                    self._save_ip_as_text("Real IP = ", res_ip)
                    return res_ip
            else:
                res_status = res[1]
                self.logger.error(
                    f"Cloudflare refuses connection for ip detection with status code {res_status} !! "
                )
                return self.get_fake_ip()


if __name__ == "__main__":
    from logger import logger

    # a = NodeIP(4, logger, True).get_current_node_ip()
    a = NodeIP(logger, force_fake_ip=False, save_path=".").get_node_ip(4)
    print(a)

#!/usr/bin/env python
# coding=utf-8
'''
Author:Tai Lei
Date:Thu Nov 22 12:09:33 2018
Info:
'''

import torch
import torch.nn as nn
# from torch.nn import functional as F


class CarlaNet(nn.Module):
    def __init__(self, structure=2, dropout_vec=None):
        super(CarlaNet, self).__init__()
        self.conv_block = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=5, stride=2),
            nn.BatchNorm2d(32),
            # nn.Dropout(self.dropout_vec[0]),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, stride=1),
            nn.BatchNorm2d(32),
            # nn.Dropout(self.dropout_vec[1]),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2),
            nn.BatchNorm2d(64),
            # nn.Dropout(self.dropout_vec[2]),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.BatchNorm2d(64),
            # nn.Dropout(self.dropout_vec[3]),
            nn.ReLU(),
            nn.Conv2d(64, 128, kernel_size=3, stride=2),
            nn.BatchNorm2d(128),
            # nn.Dropout(self.dropout_vec[4]),
            nn.ReLU(),
            nn.Conv2d(128, 128, kernel_size=3, stride=1),
            nn.BatchNorm2d(128),
            # nn.Dropout(self.dropout_vec[5]),
            nn.ReLU(),
            nn.Conv2d(128, 256, kernel_size=3, stride=1),
            nn.BatchNorm2d(256),
            # nn.Dropout(self.dropout_vec[6]),
            nn.ReLU(),
            nn.Conv2d(256, 256, kernel_size=3, stride=1),
            nn.BatchNorm2d(256),
            # nn.Dropout(self.dropout_vec[7]),
            nn.ReLU(),
        )

        self.img_fc = nn.Sequential(
                nn.Linear(8192, 512),
                nn.Dropout(0.3),
                nn.ReLU(),
                nn.Linear(512, 512),
                nn.Dropout(0.3),
                nn.ReLU(),
            )

        self.speed_fc = nn.Sequential(
                nn.Linear(1, 128),
                nn.Dropout(0.5),
                nn.ReLU(),
                nn.Linear(128, 128),
                nn.Dropout(0.5),
                nn.ReLU(),
            )

        self.emb_fc = nn.Sequential(
                nn.Linear(512+128, 512),
                nn.Dropout(0.5),
                nn.ReLU(),
            )

        self.structure = structure
        if (self.structure < 1 or self.structure > 4):
            raise("Structure must be one of 1|2|3|4")
        elif (self.structure < 4):
            self.control_branches = nn.ModuleList([
                nn.Sequential(
                    nn.Linear(512, 256),
                    nn.Dropout(0.5),
                    nn.ReLU(),
                    nn.Linear(256, 256),
                    # nn.Dropout(self.dropout_vec[i*2+14]),
                    nn.ReLU(),
                    nn.Linear(256, 3),
                ) for i in range(4)
            ])

            self.speed_branch = nn.Sequential(
                    nn.Linear(512, 256),
                    nn.Dropout(0.5),
                    nn.ReLU(),
                    nn.Linear(256, 256),
                    # nn.Dropout(self.dropout_vec[1]),
                    nn.ReLU(),
                    nn.Linear(256, 1),
                )
            if self.structure != 1:
                self.uncert_speed_branch = nn.Sequential(
                        nn.Linear(512, 256),
                        nn.ReLU(),
                        nn.Linear(256, 256),
                        nn.ReLU(),
                        nn.Linear(256, 1),
                    )
                if self.structure == 2:
                    self.uncert_control_branches = nn.ModuleList([
                        nn.Sequential(
                            nn.Linear(512, 256),
                            nn.ReLU(),
                            nn.Linear(256, 256),
                            nn.ReLU(),
                            nn.Linear(256, 3),
                        ) for i in range(4)
                    ])

                if self.structure == 3:
                    self.uncert_control_branches = nn.Sequential(
                            nn.Linear(512, 256),
                            nn.ReLU(),
                            nn.Linear(256, 256),
                            nn.ReLU(),
                            nn.Linear(256, 3),
                    )
        elif self.structure == 4:
            self.control_branches = nn.ModuleList([
                nn.Sequential(
                    nn.Linear(512, 256),
                    nn.Dropout(0.5),
                    nn.ReLU(),
                    nn.Linear(256, 256),
                    # nn.Dropout(self.dropout_vec[i*2+14]),
                    nn.ReLU(),
                    nn.Linear(256, 6),
                ) for i in range(4)
            ])

            self.speed_branch = nn.Sequential(
                    nn.Linear(512, 256),
                    nn.Dropout(0.5),
                    nn.ReLU(),
                    nn.Linear(256, 256),
                    # nn.Dropout(self.dropout_vec[1]),
                    nn.ReLU(),
                    nn.Linear(256, 2),
                )

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(
                    m.weight)
                m.bias.data.fill_(0.01)

    def forward(self, img, speed):
        img = self.conv_block(img)
        img = img.view(-1, 8192)
        img = self.img_fc(img)

        speed = self.speed_fc(speed)
        emb = torch.cat([img, speed], dim=1)
        emb = self.emb_fc(emb)

        # pure supervised regression
        if self.structure < 4:
            pred_control = torch.cat(
                [out(emb) for out in self.control_branches], dim=1)
            pred_speed = self.speed_branch(img)

            if self.structure == 1:
                return pred_control, pred_speed

            if self.structure == 2:
                log_var_control = torch.cat(
                    [un(emb) for un in self.uncert_control_branches], dim=1)
            if self.structure == 3:
                log_var_control = self.uncert_control_branches(emb)
                log_var_control = torch.cat([log_var_control for _ in range(4)],
                                            dim=1)

            log_var_speed = self.uncert_speed_branch(img)

        if self.structure == 4:
            pred_control = torch.cat(
                [out(emb).unsqueeze(1) for out in self.control_branches], dim=1)
            pred_speed = self.speed_branch(img)
            pred_control, log_var_control = torch.chunk(pred_control, 2, dim=2)
            pred_control = pred_control.view(-1, 12)
            log_var_control = log_var_control.view(-1, 12)
            pred_speed, log_var_speed = torch.chunk(pred_speed, 2, dim=1)

        return pred_control, pred_speed, log_var_control, log_var_speed
